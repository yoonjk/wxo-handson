# 규정 PDF 다시 만들기

`policies.py`의 내용을 고친 뒤 HTML을 생성하고 wkhtmltopdf로 변환합니다(한글 폰트: Noto Sans CJK KR).

```bash
python3 -c "import policies;[open(k+'.html','w',encoding='utf-8').write(policies.html_for(k)) for k in policies.POLICIES]"
for k in hr_policy_leave hr_policy_parental hr_policy_expense; do
  wkhtmltopdf -s A4 -T 18mm -B 18mm -L 16mm -R 16mm $k.html ../../data/$k.pdf
done
```
규정 수치를 바꾸면 `worksheets/lab5_test_record.csv`의 기대 동작도 함께 고치세요.
