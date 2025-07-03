
def estimate_diverse_probability(age: int) -> float:
    """
    Returns the estimated probability (as a float between 0 and 1)
    that a person of the given age identifies as 'diverse' (non-binary, inter, genderqueer, etc.)

    Source:
    - Based on self-identification surveys (e.g. Ipsos Global Pride Survey, taz 2023)
    - Estimates range around 1–2% for general population, higher in younger cohorts
    - Not based on Zensus data, which significantly underreports due to legal registration limitations

    Age groups and corresponding estimates (rounded):
        0–17     -> 1.5%
        18–29    -> 2.0%
        30–44    -> 1.0%
        45–64    -> 0.5%
        65+      -> 0.2%
    """

    if age < 0:
        raise ValueError("Age must be non-negative.")

    if age <= 17:
        return 0.015
    elif age <= 29:
        return 0.020
    elif age <= 44:
        return 0.010
    elif age <= 64:
        return 0.005
    else:
        return 0.002


