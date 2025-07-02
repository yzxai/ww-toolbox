from dataclasses import dataclass
from toolbox.tasks import EchoFilter, EchoPageSelector, EchoScan, EchoSearch, EchoPunch
from .profile import EchoProfile, EntryCoef, DiscardScheduler
from fastapi.concurrency import run_in_threadpool

current_filter: EchoFilter = None

async def apply_filter(filter: EchoFilter) -> bool:
    global current_filter
    current_filter = filter

    selector_task = EchoPageSelector()
    await run_in_threadpool(selector_task.run, filter)
    
    return True

async def scan_echo() -> list[EchoProfile]:
    scan_task = EchoScan()
    result = await run_in_threadpool(scan_task.run)

    return result

@dataclass
class AnalysisResult:
    # The current score of the echo.
    score: float 
    # The expected score after upgraded to lv 25.
    expected_score: float
    # The expected wasted exp before we decide whether to discard the echo.
    expected_wasted_exp: float
    # Probability to reach the threshold score after upgraded to lv 25. Discard strategy is disabled.
    prob_above_threshold: float
    # Probability to reach the threshold score. Discard strategy is applied.
    prob_above_threshold_with_discard: float
    # The expected total wasted exp to reach the threshold if we have infinite same echo and follow the discard strategy.
    expected_total_wasted_exp: float
    # The expected number of wasted tuners to reach the threshold if we have infinite same echo and follow the discard strategy.
    expected_total_wasted_tuner: float


async def get_brief_analysis(
    profile: EchoProfile,
    coef: EntryCoef,
    score_thres: float,
) -> AnalysisResult:
    score = profile.get_score(coef)
    expected_score = profile.get_expected_score(coef)
    prob_above_threshold = profile.prob_above_score(coef, score_thres)

    return AnalysisResult(
        score=score,
        expected_score=expected_score,
        expected_wasted_exp=None,
        prob_above_threshold=prob_above_threshold,
        prob_above_threshold_with_discard=None,
        expected_total_wasted_exp=None,
        expected_total_wasted_tuner=None
    )

async def get_analysis(
    profile: EchoProfile, 
    coef: EntryCoef, 
    score_thres: float, 
    scheduler: DiscardScheduler
) -> AnalysisResult:
    score = profile.get_score(coef)
    expected_score = profile.get_expected_score(coef)
    prob_above_threshold = profile.prob_above_score(coef, score_thres)
    prob_above_threshold_with_discard, expected_wasted_exp, expected_wasted_tuner = profile.get_statistics(coef, score_thres, scheduler)

    exp = [0, 400, 1000, 1900, 3000, 4400, 6100, 8100, 10500, 13300, 16500, 20100, 
        24200, 28800, 33900, 39600, 46000, 53100, 60900, 69600, 79100, 89600, 101100, 113700, 127500, 142600]
    
    if profile.level != 0:
        expected_wasted_exp -= exp[profile.level] * (1 - prob_above_threshold)
        expected_wasted_tuner -= (profile.level // 5) * (1 - prob_above_threshold)
    
    if prob_above_threshold_with_discard == 0:
        expected_total_wasted_exp = float("inf")
        expected_total_wasted_tuner = float("inf")
    elif prob_above_threshold_with_discard == 1:
        expected_total_wasted_exp = 0
        expected_total_wasted_tuner = 0
    else:
        # E[wasted_exp_per_echo | discard] = E[wasted_exp_per_echo] / (1 - P[above_thres])
        # E[total_wasted_exp] = ((1 / P[above_thres]) - 1) * E[wasted_exp_per_echo | discard] = E[wasted_exp_per_echo] / P[above_thres]
        expected_total_wasted_exp = expected_wasted_exp / prob_above_threshold_with_discard
        expected_total_wasted_tuner = expected_wasted_tuner / prob_above_threshold_with_discard

    return AnalysisResult(
        score=score,
        expected_score=expected_score,
        expected_wasted_exp=expected_wasted_exp,
        prob_above_threshold=prob_above_threshold,
        prob_above_threshold_with_discard=prob_above_threshold_with_discard,
        expected_total_wasted_exp=expected_total_wasted_exp,
        expected_total_wasted_tuner=expected_total_wasted_tuner
    )

async def upgrade_echo(profile: EchoProfile, work_state: dict) -> EchoProfile:
    global current_filter
    
    def blocking_code():
        # Check for cancellation before starting
        if work_state["cancel_requested"]:
            return None

        search_task = EchoSearch()
        if current_filter is not None:
            result = search_task.run(profile, work_state, main_entry_filter=current_filter.main_entry)
        else:
            result = search_task.run(profile, work_state)

        # Check for cancellation after search
        if result is None or work_state["cancel_requested"]:
            return None

        upgrade_task = EchoPunch()
        return upgrade_task.run(result, work_state)
        
    result = await run_in_threadpool(blocking_code)
    
    return result