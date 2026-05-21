# ECOM041-BANCO-DE-DADOS

## InfluxDB com dataset IoT

Este material demonstra operacoes basicas do dataset `iot_telemetry_data.csv` no InfluxDB.

## Subir o InfluxDB

Com Docker instalado, execute na raiz do projeto:

```powershell
docker compose up -d
```

Interface web:

- URL: <http://localhost:8086>
- Usuario: `admin`
- Senha: `adminadmin123`
- Organizacao: `ecom041`
- Bucket: `iot_telemetry`
- Token: `ecom041-token`

## Operacoes em Python

O script usa a API HTTP do InfluxDB 2.x e nao depende do pacote `influxdb-client`.

Ver uma amostra convertida para line protocol:

```powershell
python .\influxdb_iot_demo.py sample
```

Criar o bucket, caso ele ainda nao exista:

```powershell
python .\influxdb_iot_demo.py create-bucket
```

Inserir 1000 linhas do CSV:

```powershell
python .\influxdb_iot_demo.py insert --limit 1000
```

Inserir o CSV inteiro:

```powershell
python .\influxdb_iot_demo.py insert --limit 0
```

Consultar alguns registros de temperatura e umidade:

```powershell
python .\influxdb_iot_demo.py query --limit 20
```

Deletar os dados inseridos no intervalo do dataset:

```powershell
python .\influxdb_iot_demo.py delete
```

## Variaveis de ambiente opcionais

Os valores padrao ja combinam com o `docker-compose.yml`, mas podem ser sobrescritos:

```powershell
$env:INFLUX_URL = "http://localhost:8086"
$env:INFLUX_ORG = "ecom041"
$env:INFLUX_BUCKET = "iot_telemetry"
$env:INFLUX_TOKEN = "ecom041-token"
```

## Modelagem usada

- Measurement: `environmental_telemetry`
- Tag: `device`
- Fields: `co`, `humidity`, `light`, `lpg`, `motion`, `smoke`, `temp`
- Timestamp: `ts`, convertido de epoch em segundos para nanossegundos


# Bibliography:
- Technical Summary of the Dataset: https://www.overleaf.com/read/jjjdhnkrcxhf#aa1944
- Presentation: 
- Dataset: https://www.kaggle.com/datasets/garystafford/environmental-sensor-data-132k/data

# Authors:
- Cicero Rogério
- Rafael Ramos
- Jeyson Nascimento
