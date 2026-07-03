# Round the corners of prompt_toolkit's Frame widget globally — picks up
# every selector + multiselect + theme preview frame in one shot.
# Border attrs are read at Frame.__init__ time, so this patch applies as
# long as it lands before any Frame() construction.
from prompt_toolkit.widgets.base import Border as _Border
_Border.TOP_LEFT = "╭"      # ╭
_Border.TOP_RIGHT = "╮"     # ╮
_Border.BOTTOM_LEFT = "╰"   # ╰
_Border.BOTTOM_RIGHT = "╯"  # ╯

from . import prompter
from . import multiselect
from . import select
from . import confirm
