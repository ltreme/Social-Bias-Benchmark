from persona_generator.sampler.age_sampler import AgeSampler
from persona_generator.sampler.education_sampler import EducationSampler
from persona_generator.sampler.gender_sampler import GenderSampler
from persona_generator.sampler.occupation_sampler import OccupationSampler
from persona_generator.sampler.marriage_status_sampler import MarriageStatusSampler
from persona_generator.sampler.migration_status_sampler import MigrationStatusSampler
from persona_generator.sampler.origin_sampler import OriginSampler
from persona_generator.sampler.religion_sampler import ReligionSampler
from persona_generator.sampler.sexuality_sampler import SexualitySampler
from models.persona import PersonaDto
from models.enum.migrationstatus_enum import MigrationStatusEnum

class PersonaFactory:
    def __init__(self, 
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
                 sexuality_temperature: float = 0.0
                 ):
        self.age_sampler = AgeSampler(age_min=age_min, age_max=age_max, temperature=age_temperature)
        self.education_sampler = EducationSampler(temperature=education_temperature, exclude=education_exclude)
        self.gender_sampler = GenderSampler(temperature=gender_temperature, exclude=gender_exclude)
        self.occupation_sampler = OccupationSampler(exclude=occupation_exclude)
        self.marriage_status_sampler = MarriageStatusSampler(temperature=marriage_status_temperature, exclude=marriage_status_exclude)
        self.migration_status_sampler = MigrationStatusSampler(temperature=migration_status_temperature, exclude=migration_status_exclude)
        self.origin_sampler = OriginSampler(temperature=origin_temperature, exclude=origin_exclude)
        self.religion_sampler = ReligionSampler(temperature=religion_temperature, exclude=religion_exclude)
        self.sexuality_sampler = SexualitySampler(temperature=sexuality_temperature, exclude=sexuality_exclude)


    def create_persona(self) -> PersonaDto:
        age = self.age_sampler.sample()
        gender = self.gender_sampler.sample(age)
        education = self.education_sampler.sample(age, gender)
        occupation = self.occupation_sampler.sample(age)
        marriage_status = self.marriage_status_sampler.sample(age)
        migration_status = self.migration_status_sampler.sample(age, gender)
        origin = self.origin_sampler.sample(migration_status == MigrationStatusEnum.WITH_MIGRATION.value)
        religion = self.religion_sampler.sample(origin)
        sexuality = self.sexuality_sampler.sample()

        return PersonaDto(
            age=age,
            education=education,
            gender=gender,
            occupation=occupation,
            marriage_status=marriage_status,
            migration_status=migration_status,
            origin=origin,
            religion=religion,
            sexuality=sexuality
        )

    def create_personas(self, n: int) -> list[PersonaDto]:
        ages = self.age_sampler.sample_n(n)
        genders = self.gender_sampler.sample_n(ages)
        educations = self.education_sampler.sample_n(ages, genders)
        occupations = self.occupation_sampler.sample_n(ages)
        marriage_statuses = self.marriage_status_sampler.sample_n(ages)
        migration_statuses = self.migration_status_sampler.sample_n(ages, genders)
        origins = self.origin_sampler.sample_n([s == MigrationStatusEnum.WITH_MIGRATION.value for s in migration_statuses])
        religions = self.religion_sampler.sample_n(origins)
        sexualities = self.sexuality_sampler.sample_n(n)

        return [
            PersonaDto(
                age=age,
                education=education,
                gender=gender,
                occupation=occupation,
                marriage_status=marriage_status,
                migration_status=migration_status,
                origin=origin,
                religion=religion,
                sexuality=sexuality
            )
            for age, education, gender, occupation, marriage_status, migration_status, origin, religion, sexuality in zip(
                ages, educations, genders, occupations, marriage_statuses, migration_statuses, origins, religions, sexualities
            )
        ]