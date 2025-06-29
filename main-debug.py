from toolbox.core.profile import EchoProfile
from toolbox.utils.generic import check_privilege
from toolbox.utils.ocr import setup_ocr

check_privilege()
setup_ocr()

from toolbox.tasks.echo_punch import EchoPunch

profile = EchoProfile()
EchoPunch().run(profile, {"cancel_requested": False})