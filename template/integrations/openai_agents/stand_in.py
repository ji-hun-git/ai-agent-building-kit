"""The template's stand-in model behind the SDK's Model interface, so the tour and the tests run offline.

examples.hr.stand_in.StandIn obeys instructions it finds in documents, which is the point: the port has
to contain a model that does the wrong thing, not one that happens to behave. This class only
translates: SDK input items become the kit's message dicts, and a kit Reply becomes SDK output items.
"""

from agents import Model, ModelResponse, Usage
from agents.testing import assistant_message, function_call

from examples.hr.stand_in import StandIn

from . import ERRORS, text_of


def messages(items) -> list[dict]:
    """SDK input items as the kit's message dicts, the shape StandIn reads."""
    if isinstance(items, str):
        items = [{"role": "user", "content": items}]
    names, out = {}, []
    for item in items:
        kind = item.get("type", "message")
        if kind == "function_call":
            names[item["call_id"]] = item["name"]
        elif kind == "function_call_output":
            text = text_of(item["output"])
            out.append({"role": "tool", "name": names.get(item["call_id"], ""), "content": text,
                        "is_error": text.startswith(ERRORS)})
        elif kind == "message" and item.get("role") in ("user", "assistant"):
            out.append({"role": item["role"], "content": text_of(item["content"])})
    return out


class StandInModel(Model):
    def __init__(self):
        self.stand_in, self.replies = StandIn(), 0

    async def get_response(self, system_instructions, input, model_settings, tools, output_schema, handoffs,
                           tracing, *, previous_response_id, conversation_id, prompt) -> ModelResponse:
        reply = self.stand_in(system_instructions or "", messages(input), [])
        self.replies += 1
        output = [assistant_message(reply.text, item_id=f"msg_{self.replies}")] if reply.text else []
        output += [function_call(c.name, c.args, call_id=c.id) for c in reply.calls]
        return ModelResponse(output=output, usage=Usage(requests=1), response_id=None)

    async def stream_response(self, *args, **kwargs):
        raise NotImplementedError("the stand-in answers whole replies; use Runner.run")
        yield  # an async generator, as the interface expects
