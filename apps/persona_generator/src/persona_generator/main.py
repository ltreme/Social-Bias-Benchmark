import argparse
import csv
import uuid

from persona_generator.sampler.age_sampler import AgeSampler
from persona_generator.sampler.education_sampler import EducationSampler
from persona_generator.sampler.gender_sampler import GenderSampler
from persona_generator.sampler.marriage_status_sampler import MarriageStatusSampler
from persona_generator.sampler.migration_status_sampler import MigrationStatusSampler
from persona_generator.sampler.occupation_sampler import OccupationSampler
from persona_generator.sampler.origin_sampler import OriginSampler
from persona_generator.sampler.religion_sampler import ReligionSampler
from persona_generator.sampler.sexuality_sampler import SexualitySampler
from shared.core_types import MigrationStatusEnum
from shared.paths import PATH_PERSONAS_CSV


def sample(
    n: int,
    out: str,
    age_min: int = 0,
    age_max: int = 100,
    age_temperature: float = 0.0,
    education_temperature: float = 0.0,
    education_exclude: list = None,
    gender_temperature: float = 0.0,
    gender_exclude: list = None,
    occupation_exclude: list = None,
    marriage_status_temperature: float = 0.0,
    marriage_status_exclude: list = None,
    migration_status_exclude: list = None,
    migration_status_temperature: float = 0.0,
    origin_temperature: float = 0.0,
    origin_exclude: list = None,
    religion_temperature: float = 0.0,
    religion_exclude: list = None,
    sexuality_exclude: list = None,
    sexuality_temperature: float = 0.0,
):

    age_sampler = AgeSampler(
        age_min=age_min, age_max=age_max, temperature=age_temperature
    )
    education_sampler = EducationSampler(
        temperature=education_temperature, exclude=education_exclude
    )
    gender_sampler = GenderSampler(
        temperature=gender_temperature, exclude=gender_exclude
    )
    occupation_sampler = OccupationSampler(exclude=occupation_exclude)
    marriage_status_sampler = MarriageStatusSampler(
        temperature=marriage_status_temperature, exclude=marriage_status_exclude
    )
    migration_status_sampler = MigrationStatusSampler(
        temperature=migration_status_temperature, exclude=migration_status_exclude
    )
    origin_sampler = OriginSampler(
        temperature=origin_temperature, exclude=origin_exclude
    )
    religion_sampler = ReligionSampler(
        temperature=religion_temperature, exclude=religion_exclude
    )
    sexuality_sampler = SexualitySampler(
        temperature=sexuality_temperature, exclude=sexuality_exclude
    )

    ages = age_sampler.sample_n(n)
    genders = gender_sampler.sample_n(ages)
    educations = education_sampler.sample_n(ages, genders)
    occupations = occupation_sampler.sample_n(ages)
    marriage_statuses = marriage_status_sampler.sample_n(ages)
    migration_statuses = migration_status_sampler.sample_n(ages, genders)
    with_migrations = [
        ms == MigrationStatusEnum.WITH_MIGRATION.value for ms in migration_statuses
    ]
    origins = origin_sampler.sample_n(with_migrations)
    religions = religion_sampler.sample_n(origins)
    sexualities = sexuality_sampler.sample_n(n)

    if len(ages) != n:
        raise ValueError("Sampling did not return the expected number of ages.")
    if len(genders) != n:
        raise ValueError("Sampling did not return the expected number of genders.")
    if len(educations) != n:
        raise ValueError("Sampling did not return the expected number of educations.")
    if len(occupations) != n:
        raise ValueError("Sampling did not return the expected number of occupations.")
    if len(marriage_statuses) != n:
        raise ValueError(
            "Sampling did not return the expected number of marriage statuses."
        )
    if len(migration_statuses) != n:
        raise ValueError(
            "Sampling did not return the expected number of migration statuses."
        )
    if len(origins) != n:
        raise ValueError("Sampling did not return the expected number of origins.")
    if len(religions) != n:
        raise ValueError("Sampling did not return the expected number of religions.")
    if len(sexualities) != n:
        raise ValueError("Sampling did not return the expected number of sexualities.")

    with open(out, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = [
            "uuid",
            "age",
            "gender",
            "education",
            "occupation",
            "marriage_status",
            "migration_status",
            "origin",
            "religion",
            "sexuality",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for i in range(n):
            writer.writerow(
                {
                    "uuid": str(uuid.uuid4()),
                    "age": ages[i],
                    "gender": genders[i],
                    "education": educations[i],
                    "occupation": occupations[i],
                    "marriage_status": marriage_statuses[i],
                    "migration_status": migration_statuses[i],
                    "origin": origins[i],
                    "religion": religions[i],
                    "sexuality": sexualities[i],
                }
            )


def main():
    parser = argparse.ArgumentParser(description="Persona Generator")
    parser.add_argument(
        "--n", type=int, default=1000, help="Number of personas to generate"
    )
    parser.add_argument(
        "--out",
        type=str,
        default=PATH_PERSONAS_CSV,
        help="Output CSV file",
    )
    parser.add_argument("--age_from", type=int, default=0, help="Minimum age")
    parser.add_argument("--age_to", type=int, default=100, help="Maximum age")
    parser.add_argument(
        "--age_temperature",
        type=float,
        default=0.0,
        help="Sampling temperature for age",
    )
    parser.add_argument(
        "--education_temperature",
        type=float,
        default=0.0,
        help="Sampling temperature for education",
    )
    parser.add_argument(
        "--education_exclude",
        nargs="*",
        default=None,
        help="List of education levels to exclude",
    )
    parser.add_argument(
        "--gender_temperature",
        type=float,
        default=0.0,
        help="Sampling temperature for gender",
    )
    parser.add_argument(
        "--gender_exclude", nargs="*", default=None, help="List of genders to exclude"
    )
    parser.add_argument(
        "--occupation_exclude",
        nargs="*",
        default=None,
        help="List of occupations to exclude",
    )
    parser.add_argument(
        "--marriage_status_temperature",
        type=float,
        default=0.0,
        help="Sampling temperature for marriage status",
    )
    parser.add_argument(
        "--marriage_status_exclude",
        nargs="*",
        default=None,
        help="List of marriage statuses to exclude",
    )
    parser.add_argument(
        "--migration_status_temperature",
        type=float,
        default=0.0,
        help="Sampling temperature for migration status",
    )
    parser.add_argument(
        "--migration_status_exclude",
        nargs="*",
        default=None,
        help="List of migration statuses to exclude",
    )
    parser.add_argument(
        "--origin_temperature",
        type=float,
        default=0.0,
        help="Sampling temperature for origin",
    )
    parser.add_argument(
        "--origin_exclude", nargs="*", default=None, help="List of origins to exclude"
    )
    parser.add_argument(
        "--religion_temperature",
        type=float,
        default=0.0,
        help="Sampling temperature for religion",
    )
    parser.add_argument(
        "--religion_exclude",
        nargs="*",
        default=None,
        help="List of religions to exclude",
    )
    parser.add_argument(
        "--sexuality_temperature",
        type=float,
        default=0.0,
        help="Sampling temperature for sexuality",
    )
    parser.add_argument(
        "--sexuality_exclude",
        nargs="*",
        default=None,
        help="List of sexualities to exclude",
    )
    args = parser.parse_args()
    sample(
        n=args.n,
        out=args.out,
        age_min=args.age_from,
        age_max=args.age_to,
        age_temperature=args.age_temperature,
        education_temperature=args.education_temperature,
        education_exclude=args.education_exclude,
        gender_temperature=args.gender_temperature,
        gender_exclude=args.gender_exclude,
        occupation_exclude=args.occupation_exclude,
        marriage_status_temperature=args.marriage_status_temperature,
        marriage_status_exclude=args.marriage_status_exclude,
        migration_status_temperature=args.migration_status_temperature,
        migration_status_exclude=args.migration_status_exclude,
        origin_temperature=args.origin_temperature,
        origin_exclude=args.origin_exclude,
        religion_temperature=args.religion_temperature,
        religion_exclude=args.religion_exclude,
        sexuality_temperature=args.sexuality_temperature,
        sexuality_exclude=args.sexuality_exclude,
    )


if __name__ == "__main__":

    main()
