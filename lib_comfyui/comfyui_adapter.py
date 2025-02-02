import atexit
import os
from torch import multiprocessing
from lib_comfyui import async_comfyui_loader, webui_settings, webui_paths, ipc, torch_utils, webui_proxies
from lib_comfyui.comfyui_context import ComfyuiContext
from modules import shared


comfyui_process = None
multiprocessing_spawn = multiprocessing.get_context('spawn')


def start():
    install_location = webui_settings.get_install_location()
    if not os.path.exists(install_location):
        return

    if not getattr(shared.opts, 'comfyui_enabled', True):
        return

    ipc.start_callback_listeners()
    atexit.register(ipc.stop_callback_listeners)
    start_comfyui_process(install_location)


def start_comfyui_process(install_location):
    global comfyui_process

    with ComfyuiContext():
        comfyui_process = multiprocessing_spawn.Process(
            target=async_comfyui_loader.main,
            args=(
                install_location,
                webui_paths.get_folder_paths(),
                {**ipc.get_current_process_queues(), **ipc.current_process_queues}
            ),
            daemon=True,
        )
        comfyui_process.start()


def stop():
    stop_comfyui_process()
    ipc.stop_callback_listeners()
    atexit.unregister(ipc.stop_callback_listeners)


def stop_comfyui_process():
    global comfyui_process
    if comfyui_process is None:
        return

    comfyui_process.terminate()
    comfyui_process = None
