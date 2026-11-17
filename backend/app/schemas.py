from marshmallow import Schema as MarshmallowSchema
from marshmallow import pre_load


def _trim(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return [_trim(item) for item in value]
    if isinstance(value, dict):
        return {key: _trim(item) for key, item in value.items()}
    return value


class Schema(MarshmallowSchema):
    @pre_load
    def trim_text(self, data, **kwargs):
        return _trim(data) if isinstance(data, dict) else data
