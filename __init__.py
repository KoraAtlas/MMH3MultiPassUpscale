from comfy_api.latest import ComfyExtension
from typing_extensions import override

from .nodes.multipass import MMH3MultiPassSamplerCustomAdvanced

WEB_DIRECTORY = "./web"


class MMH3MultiPassExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type]:
        return [MMH3MultiPassSamplerCustomAdvanced]


async def comfy_entrypoint() -> MMH3MultiPassExtension:
    return MMH3MultiPassExtension()
