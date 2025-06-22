from toolbox.config.profile import EchoProfile
from toolbox.tasks.echo_task import Page
from toolbox.utils.generic import run_as_admin
from toolbox.utils.ocr import setup_ocr
import time

run_as_admin()
setup_ocr()

from toolbox.utils.logger import logger
from toolbox.core.interaction import Interaction

interaction = Interaction()
interaction.connect()

from toolbox.tasks import EchoScan, EchoSearch, EchoPunch

target_profile = EchoProfile(
    level=15, 
    cri_dmg=15.0,
    cri_rate=6.9,
    def_rate=10.0
)

assert target_profile.validate() == True

search_task = EchoSearch()
found = search_task.run(target_profile)

assert found == True

if found:
    punch_task = EchoPunch()
    target_profile = punch_task.run(target_profile)

search_task.to_page(Page.MAIN)
logger.info(f"Punched target profile: {target_profile}")

logger.info('Done')
