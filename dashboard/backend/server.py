import asyncio
from pathlib import Path
from typing import Dict, Set
from contextlib import asynccontextmanager

import json

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response

from .models import (
    Project, ProjectConfig, ProjectStatus, StepStatus,
    CreateProjectRequest, UpdateConfigRequest, UpdateScriptRequest,
    RegenerateScriptRequest, ConfigOptions, ProgressUpdate, VideoScript
)
from .project_manager import ProjectManager
from .pipeline_runner import PipelineRunner


PROJECTS_DIR = Path(__file__).parent.parent.parent / "projects"
FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"
VOICES_DIR = Path.home() / ".cache" / "video_studio" / "xtts_voices" / "samples"
MAPPINGS_FILE = Path.home() / ".cache" / "video_studio" / "xtts_voices" / "voice_mappings.json"

project_manager = ProjectManager(PROJECTS_DIR)
active_websockets: Dict[str, Set[WebSocket]] = {}
running_pipelines: Dict[str, asyncio.Task] = {}


def progress_callback(project_id: str, step: str, status: StepStatus, progress: float, message: str):
    update = ProgressUpdate(
        project_id=project_id,
        step=step,
        status=status,
        progress=progress,
        message=message
    )
    asyncio.create_task(broadcast_progress(project_id, update))


async def broadcast_progress(project_id: str, update: ProgressUpdate):
    if project_id not in active_websockets:
        return

    message = update.model_dump_json()
    dead_connections = []

    for ws in active_websockets[project_id]:
        try:
            await ws.send_text(message)
        except Exception:
            dead_connections.append(ws)

    for ws in dead_connections:
        active_websockets[project_id].discard(ws)


pipeline_runner = PipelineRunner(project_manager, progress_callback)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    for task in running_pipelines.values():
        task.cancel()


app = FastAPI(title="Video Studio Dashboard", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/projects")
async def list_projects():
    projects = project_manager.list_all()
    return {"projects": [p.model_dump() for p in projects]}


@app.post("/api/projects")
async def create_project(request: CreateProjectRequest):
    project = project_manager.create(request.config)
    return project.model_dump()


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    project = project_manager.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.model_dump()


@app.put("/api/projects/{project_id}/config")
async def update_config(project_id: str, request: UpdateConfigRequest):
    project = project_manager.update_config(project_id, request.config)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.model_dump()


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    if project_id in running_pipelines:
        running_pipelines[project_id].cancel()
        del running_pipelines[project_id]

    if not project_manager.delete(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "deleted"}


@app.post("/api/projects/{project_id}/start")
async def start_pipeline(project_id: str):
    project = project_manager.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project_id in running_pipelines and not running_pipelines[project_id].done():
        raise HTTPException(status_code=400, detail="Pipeline already running")

    task = asyncio.create_task(pipeline_runner.run_all(project_id))
    running_pipelines[project_id] = task

    return {"status": "started"}


@app.post("/api/projects/{project_id}/pause")
async def pause_pipeline(project_id: str):
    if project_id not in running_pipelines:
        raise HTTPException(status_code=400, detail="No pipeline running")

    pipeline_runner.request_pause()
    return {"status": "pause_requested"}


@app.post("/api/projects/{project_id}/step/{step_name}")
async def run_single_step(project_id: str, step_name: str):
    project = project_manager.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    valid_steps = ["script", "voice", "music", "visuals", "assembly", "thumbnail"]
    if step_name not in valid_steps:
        raise HTTPException(status_code=400, detail=f"Invalid step: {step_name}")

    result = await pipeline_runner.run_step(project_id, step_name)
    if not result:
        raise HTTPException(status_code=500, detail="Step execution failed")

    return result.model_dump()


@app.put("/api/projects/{project_id}/script")
async def update_script(project_id: str, request: UpdateScriptRequest):
    project = project_manager.set_script(project_id, request.script)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.output_dir:
        script_path = Path(project.output_dir) / "script.json"
        with open(script_path, "w") as f:
            f.write(request.script.model_dump_json(indent=2))

    return project.model_dump()


@app.post("/api/projects/{project_id}/regenerate")
async def regenerate_script(project_id: str, request: RegenerateScriptRequest = None):
    project = project_manager.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project_manager.reset_steps(project_id, from_step="script")

    result = await pipeline_runner.run_step(project_id, "script")
    if not result:
        raise HTTPException(status_code=500, detail="Script regeneration failed")

    return result.model_dump()


@app.post("/api/projects/{project_id}/reset")
async def reset_project(project_id: str, from_step: str = None):
    project = project_manager.reset_steps(project_id, from_step)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.model_dump()


@app.get("/api/config/options")
async def get_config_options():
    return ConfigOptions().model_dump()


@app.get("/api/voices")
async def list_voices():
    if not VOICES_DIR.exists():
        return {"voices": [], "mappings": {}}

    voices = []
    for wav_file in sorted(VOICES_DIR.glob("*.wav")):
        stat = wav_file.stat()
        voices.append({
            "name": wav_file.stem,
            "size_kb": round(stat.st_size / 1024, 1),
            "path": str(wav_file),
        })

    mappings = {}
    if MAPPINGS_FILE.exists():
        with open(MAPPINGS_FILE) as f:
            mappings = json.load(f)

    return {"voices": voices, "mappings": mappings}


@app.get("/api/voices/{voice_name}/audio")
async def get_voice_audio(voice_name: str):
    voice_path = VOICES_DIR / f"{voice_name}.wav"
    if not voice_path.exists():
        raise HTTPException(status_code=404, detail="Voice not found")

    with open(voice_path, "rb") as f:
        audio_data = f.read()

    return Response(content=audio_data, media_type="audio/wav")


@app.get("/api/voices/mappings")
async def get_voice_mappings():
    mappings = {}
    if MAPPINGS_FILE.exists():
        with open(MAPPINGS_FILE) as f:
            mappings = json.load(f)
    return mappings


@app.post("/api/voices/mappings")
async def update_voice_mappings(mappings: dict):
    MAPPINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MAPPINGS_FILE, "w") as f:
        json.dump(mappings, f, indent=2)
    return mappings


@app.websocket("/ws/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    await websocket.accept()

    if project_id not in active_websockets:
        active_websockets[project_id] = set()
    active_websockets[project_id].add(websocket)

    try:
        project = project_manager.get(project_id)
        if project:
            await websocket.send_json({"type": "init", "project": project.model_dump()})

        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        if project_id in active_websockets:
            active_websockets[project_id].discard(websocket)


if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = FRONTEND_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIR / "index.html")


def run_server(host: str = "0.0.0.0", port: int = 8450):
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
