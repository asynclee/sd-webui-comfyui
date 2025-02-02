import functools
import multiprocessing
import contextlib

from lib_comfyui import ipc


class PromptQueueTracker:
    done_event = multiprocessing.Event()
    put_event = multiprocessing.Event()
    tracked_id = None
    original_id = None
    queue_instance = None
    server_instance = None

    @ipc.confine_to('comfyui')
    @staticmethod
    def setup_tracker_id():
        PromptQueueTracker.original_id = PromptQueueTracker.tracked_id
        PromptQueueTracker.tracked_id = PromptQueueTracker.server_instance.number
        PromptQueueTracker.put_event.clear()
        PromptQueueTracker.done_event.clear()

    @ipc.confine_to('comfyui')
    @staticmethod
    def wait_until_done():
        was_put = PromptQueueTracker.put_event.wait(timeout=3)
        if not was_put:
            PromptQueueTracker.tracked_id = PromptQueueTracker.original_id
            return

        if not PromptQueueTracker.tracked_id_present():
            return

        PromptQueueTracker.done_event.wait()

    @ipc.confine_to('comfyui')
    @staticmethod
    def tracked_id_present():
        with PromptQueueTracker.queue_instance.mutex:
            for v in PromptQueueTracker.queue_instance.currently_running.values():
                if abs(v[0]) == PromptQueueTracker.tracked_id:
                    return True
            for x in PromptQueueTracker.queue_instance.queue:
                if abs(x[0]) == PromptQueueTracker.tracked_id:
                    return True
            return False

    @staticmethod
    def patched__init__(self, server_instance):
        prompt_queue = self
        PromptQueueTracker.server_instance = server_instance
        PromptQueueTracker.queue_instance = self

        def patched_put(item, *args, original_put, **kwargs):
            with prompt_queue.mutex:
                if abs(item[0]) == PromptQueueTracker.tracked_id:
                    PromptQueueTracker.put_event.set()

                with AlreadyInUseMutex(prompt_queue):
                    return original_put(item, *args, **kwargs)
        
        prompt_queue.put = functools.partial(patched_put, original_put=prompt_queue.put)

        # task_done
        def patched_task_done(item_id, output, *args, original_task_done, **kwargs):
            with prompt_queue.mutex:
                v = prompt_queue.currently_running[item_id]
                if abs(v[0]) == PromptQueueTracker.tracked_id:
                    PromptQueueTracker.done_event.set()

                with AlreadyInUseMutex(prompt_queue):
                    return original_task_done(item_id, output, *args, **kwargs)

        prompt_queue.task_done = functools.partial(patched_task_done, original_task_done=prompt_queue.task_done)

        # wipe_queue
        def patched_wipe_queue(*args, original_wipe_queue, **kwargs):
            with prompt_queue.mutex:
                should_release_webui = True
                for _, v in prompt_queue.currently_running.items():
                    if abs(v[0]) == PromptQueueTracker.tracked_id:
                        should_release_webui = False

                if should_release_webui:
                    PromptQueueTracker.done_event.set()

                with AlreadyInUseMutex(prompt_queue):
                    return original_wipe_queue(*args, **kwargs)

        prompt_queue.wipe_queue = functools.partial(patched_wipe_queue, original_wipe_queue=prompt_queue.wipe_queue)

        # delete_queue_item
        def patched_delete_queue_item(function, *args, original_delete_queue_item, **kwargs):
            def patched_function(x):
                res = function(x)
                if res and abs(x[0]) == PromptQueueTracker.tracked_id:
                    PromptQueueTracker.done_event.set()
                return res

            return original_delete_queue_item(patched_function, *args, **kwargs)

        prompt_queue.delete_queue_item = functools.partial(patched_delete_queue_item, original_delete_queue_item=prompt_queue.delete_queue_item)


class AlreadyInUseMutex:
    def __init__(self, prompt_queue):
        self.prompt_queue = prompt_queue
        self.original_mutex = prompt_queue.mutex

    def __enter__(self):
        self.prompt_queue.mutex = contextlib.nullcontext()
        return self.original_mutex

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.prompt_queue.mutex = self.original_mutex


def add_queue__init__patch(callback):
    import execution
    original_init = execution.PromptQueue.__init__

    def patched_PromptQueue__init__(self, server, *args, **kwargs):
        original_init(self, server, *args, **kwargs)
        callback(self, server, *args, **kwargs)

    execution.PromptQueue.__init__ = patched_PromptQueue__init__


def patch_prompt_queue():
    add_queue__init__patch(PromptQueueTracker.patched__init__)
