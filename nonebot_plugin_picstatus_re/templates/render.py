from typing import TYPE_CHECKING
from cookit import auto_convert_byte
from cookit.jinja import all_filters
from cookit.jinja.filters import cookit_global_filter
from ..util import format_cpu_freq

if TYPE_CHECKING:
    import jinja2

jinja_filter = type(cookit_global_filter)(all_filters.copy())

def register_global_filter_to(env: "jinja2.Environment"):
    env.filters.update(jinja_filter.data)

jinja_filter(format_cpu_freq)

@jinja_filter
def percent_to_color(percent: float) -> str:
    if percent < 70:
        return "prog-low"
    if percent < 90:
        return "prog-medium"
    return "prog-high"

@jinja_filter
def auto_convert_unit(value: float, **kw) -> str:
    return auto_convert_byte(value=value, with_space=False, **kw)
