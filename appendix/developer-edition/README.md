

WO_DEVELOPER_EDITION_SOURCE

# Generate ENTITLEMENT_KEY : 

어디서 발급받나. 
myibm.ibm.com/products-services/containerlibrary 에 접속 (IBMid로 로그인). 
"Container software and entitlement keys" 페이지로 이동. 
Entitlement keys 섹션에서 "Copy" 버튼으로 키 복사 (없으면 "Add new key"로 발급). 
복사한 긴 문자열이 바로 entitlement key입니다. 


docker login -u cp -p <ENTITLEMENT_KEY> cp.icr.io

# Pull minio
```bash
docker pull pgsty/minio:latest
docker tag  pgsty/minio:latest minio/minio:latest
# mc(클라이언트)는 포크 태그 확인 후 동일 방식으로
# 1) 포크 이미지 받기
docker pull pgsty/minio:latest

# 2) compose가 찾는 이름으로 태그 복제
docker tag pgsty/minio:latest minio/minio:latest

# 3) mc(클라이언트)도 동일하게 — 포크 레포에 있는 mc 태그 확인 후
#    (예: pgsty/mc 가 있으면)
docker pull pgsty/mc:latest 2>/dev/null && docker tag pgsty/mc:latest minio/mc:latest
docker pull quay.io/minio/mc:latest && docker tag quay.io/minio/mc:latest minio/mc:latest
```
# Starting watsonx orchestrate developer edition
orchestrate server start -e .env --with-doc-processing 