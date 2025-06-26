from toolbox.core.profile import EchoProfile
from toolbox.utils.generic import run_as_admin
from toolbox.utils.ocr import setup_ocr

run_as_admin()
setup_ocr()

from toolbox.tasks.echo_punch import EchoPunch

profile = EchoProfile()
EchoPunch().run(profile, {"cancel_requested": False})