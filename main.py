from toolbox.utils.generic import run_as_admin
import time

run_as_admin()

from toolbox.utils.logger import logger
from toolbox.core.interaction import Interaction

interaction = Interaction()
interaction.connect()

interaction.click(0.28, 0.70)

logger.info('Done')
