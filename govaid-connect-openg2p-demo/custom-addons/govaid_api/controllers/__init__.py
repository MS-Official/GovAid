"""
GovAid API — Controllers Package

Import order matters: main must come first (auth helpers),
then individual resource controllers.
"""
from . import main
from . import beneficiaries
from . import programs
from . import eligibility
from . import payments
from . import grievances
