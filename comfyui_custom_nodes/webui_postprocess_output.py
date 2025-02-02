from torchvision.transforms.functional import to_pil_image
from lib_comfyui import global_state


expected_node_types = []


class WebuiPostprocessOutput:
    images = None

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", ),
            },
        }
    RETURN_TYPES = ()
    FUNCTION = "fetch_images"

    CATEGORY = "webui"

    OUTPUT_NODE = True

    def fetch_images(self, images):
        tab_name = global_state.tab_name
        key = f'{tab_name}_postprocess_output_images'
        images_pil = [to_pil_image(img) for img in images.permute(0, 3, 1, 2)]
        generated_images = getattr(global_state, key, [])
        generated_images.extend(images_pil)
        setattr(global_state, key, generated_images)
        return []


NODE_CLASS_MAPPINGS = {
    "PostprocessToWebui": WebuiPostprocessOutput,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PostprocessToWebui": 'Postprocess To Webui',
}
