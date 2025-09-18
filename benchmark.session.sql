select
    p.uuid,
    max(case when apa.attribute_key = 'name' then apa.value end)       as name,
    p.age, p.gender, p.education, p.occupation, p.marriage_status, p.religion, p.sexuality,
    c.country_de, c.population, c.region, c.country_code_alpha2, c.subregion,
    max(case when apa.attribute_key = 'appearance' then apa.value end) as appearance,
    max(case when apa.attribute_key = 'biography' then apa.value end)  as biography,
    br.rating
from persona p
join additionalpersonaattributes apa
  on p.uuid = apa.persona_uuid_id
join country c
  on p.origin_id = c.id
left join benchmarkresult br
  on p.uuid = br.persona_uuid_id
 and br.model_name = apa.model_name
where p.gen_id = 12
  and apa.model_name = 'stelterlab/Mistral-Small-3.2-24B-Instruct-2506-FP8'
  and br.question_uuid = '33ab83eb-3b75-492f-b1dd-b56ae29c6a7f'
group by p.uuid;
