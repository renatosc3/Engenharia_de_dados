create schema if not exists prata;

create or replace view prata.livros as
with mais_recentes as (
    select
        payload,
        _ingestao_em,
        row_number() over (
            partition by btrim(payload->>'upc') -- R1, R7
            order by _ingestao_em desc, id desc -- R1
        ) as posicao
    from bronze.livros
)
select
    btrim(payload->>'upc') as upc, -- R7
    btrim(payload->>'titulo') as titulo, -- R7
    case
        when btrim(payload->>'categoria_raw') in ('Default', 'Add a comment') then 'Sem categoria' -- R6, R7
        else btrim(payload->>'categoria_raw') -- R7
    end as categoria,
    nullif(regexp_replace(payload->>'preco_raw', '[^0-9.]', '', 'g'), '')::numeric(10,2) as preco_gbp, -- R2
    case btrim(payload->>'rating_raw') -- R3, R7
        when 'star-rating One' then 1 -- R3
        when 'star-rating Two' then 2 -- R3
        when 'star-rating Three' then 3 -- R3
        when 'star-rating Four' then 4 -- R3
        when 'star-rating Five' then 5 -- R3
    end as rating,
    coalesce(substring(payload->>'estoque_raw' from '\(([0-9]+) available\)')::int, 0) as estoque_qtd, -- R4
    nullif(btrim(payload->>'n_reviews_raw'), '')::int as n_reviews, -- R5, R7
    btrim(payload->>'url') as url, -- R7
    _ingestao_em
from mais_recentes
where posicao = 1; -- R1
