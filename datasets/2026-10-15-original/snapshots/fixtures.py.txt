"""Deterministic synthetic inputs and external acceptance tests."""
import json
from pathlib import Path

GO_BROKEN = '''package records
import ("bufio"; "encoding/json"; "io")
type Record struct { ID string `json:"id"`; Value int `json:"value"` }
func ReadUnique(r io.Reader, maxBytes int) ([]Record, error) {
 s := bufio.NewScanner(r)
 out := []Record{}
 for s.Scan() { var v Record; if err := json.Unmarshal(s.Bytes(), &v); err != nil { continue }; out = append(out, v) }
 return out, nil
}
'''
GO_VISIBLE = '''package records
import ("strings"; "testing")
func TestBasic(t *testing.T) { r,e:=ReadUnique(strings.NewReader("{\\"id\\":\\"a\\",\\"value\\":1}\\n"),100); if e!=nil || len(r)!=1 || r[0].ID!="a" { t.Fatalf("%v %v",r,e) } }
func TestDeduplicate(t *testing.T) { r,e:=ReadUnique(strings.NewReader("{\\"id\\":\\"a\\",\\"value\\":1}\\n{\\"id\\":\\"a\\",\\"value\\":2}"),100); if e!=nil || len(r)!=1 || r[0].Value!=1 { t.Fatalf("%v %v",r,e) } }
'''
GO_HIDDEN = '''package records
import ("strings"; "testing"; "errors"; "io"; "reflect"; "fmt")
type brokenReader struct{}
func (brokenReader) Read(p []byte)(int,error){return 0,errors.New("broken-reader")}
func TestAcceptance(t *testing.T){
 cases:=[]struct{name,input string;limit int;want []Record;bad bool}{
 {"empty","",100,[]Record{},false},
 {"blank","\\n  \\n\\t\\n",100,[]Record{},false},
 {"order","{\\"id\\":\\"z\\",\\"value\\":1}\\n{\\"id\\":\\"a\\",\\"value\\":2}\\n{\\"id\\":\\"z\\",\\"value\\":9}",100,[]Record{{"z",1},{"a",2}},false},
 {"invalid","{\\"id\\":\\"a\\"}\\nno",100,nil,true},
 {"missing-id","{\\"value\\":2}",100,nil,true},
 {"blank-id","{\\"id\\":\\"  \\"}",100,nil,true},
 {"zero-limit","",0,nil,true},
 {"too-long",strings.Repeat("x",101),100,nil,true},
 {"crlf","{\\"id\\":\\"a\\",\\"value\\":1}\\r\\n",100,[]Record{{"a",1}},false},
 }
 for _,c:=range cases{t.Run(c.name,func(t *testing.T){got,e:=ReadUnique(strings.NewReader(c.input),c.limit);if (e!=nil)!=c.bad{t.Fatalf("error=%v",e)};if c.bad{if got!=nil{t.Fatal("partial output")};return};if len(got)!=len(c.want)||len(got)>0&&!reflect.DeepEqual(got,c.want){t.Fatalf("got=%v want=%v",got,c.want)}})}
 _,e:=ReadUnique(brokenReader{},100);if e==nil||!strings.Contains(e.Error(),"broken-reader"){t.Fatalf("reader error lost: %v",e)}
 long:=fmt.Sprintf("{\\"id\\":\\"%s\\",\\"value\\":7}",strings.Repeat("a",70000));got,e:=ReadUnique(strings.NewReader(long),len(long));if e!=nil||len(got)!=1{t.Fatalf("long valid record: %v",e)}
 got,e=ReadUnique(io.MultiReader(strings.NewReader("{\\"id\\":\\"a\\"}\\n"),brokenReader{}),100);if e==nil||got!=nil{t.Fatalf("partial reader failure: %v %v",got,e)}
}
'''
PY_BROKEN = '''import csv
from io import StringIO

def aggregate(text):
    totals = {}
    for row in csv.DictReader(StringIO(text)):
        currency = row['currency']
        totals[currency] = totals.get(currency, 0.0) + float(row['amount'])
    return totals
'''
PY_VISIBLE = '''from decimal import Decimal
import unittest
from aggregate import aggregate
class Visible(unittest.TestCase):
 def test_decimal(self):
  self.assertEqual(aggregate('id,currency,kind,amount\\na,RUB,payment,0.10\\nb,RUB,payment,0.20\\n'), {'RUB':Decimal('0.30')})
 def test_refund(self):
  self.assertEqual(aggregate('id,currency,kind,amount\\na,USD,payment,10\\nb,USD,refund,3\\n'), {'USD':Decimal('7.00')})
'''
PY_HIDDEN = '''from decimal import Decimal
import unittest
from aggregate import aggregate
H='id,currency,kind,amount\\n'
class Acceptance(unittest.TestCase):
 def test_empty(self):
  self.assertEqual(aggregate(''),{})
  self.assertEqual(aggregate(H),{})
 def test_round_each_half_up(self):
  self.assertEqual(aggregate(H+'a,EUR,payment,1.005\\nb,EUR,payment,1.005\\nc,EUR,refund,0.005\\n'),{'EUR':Decimal('2.01')})
 def test_duplicate(self):
  self.assertEqual(aggregate(H+'a,RUB,payment,2\\na,RUB,payment,2.000\\n'),{'RUB':Decimal('2.00')})
 def test_conflicting_duplicate(self):
  with self.assertRaises(ValueError):aggregate(H+'a,RUB,payment,2\\na,RUB,refund,2\\n')
 def test_invalid_rows(self):
  for row in ['a,RUB,payment,-1','a,RUB,payment,NaN','a,RUB,payment,Infinity','a,RUB,payment,1e3','a,RUB,payment,1.','a,RUB,payment,+1','a,GBP,payment,2','a,RUB,other,2',',RUB,payment,2','a,RUB,payment','a,RUB,payment,2,extra']:
   with self.subTest(row=row):
    with self.assertRaises(ValueError):aggregate(H+row+'\\n')
 def test_headers(self):
  for value in ['id,currency,amount\\n','id,currency,kind,amount,extra\\n','id,id,kind,amount\\n']:
   with self.assertRaises(ValueError):aggregate(value)
 def test_whitespace(self):
  self.assertEqual(aggregate(H+' a , RUB , payment , 1.235 \\nb,RUB,refund,0.24\\n'),{'RUB':Decimal('1.00')})
 def test_types_and_currencies(self):
  got=aggregate(H+'a,USD,payment,0\\nb,EUR,refund,1\\n')
  self.assertEqual(got,{'USD':Decimal('0.00'),'EUR':Decimal('-1.00')})
  self.assertTrue(all(isinstance(v,Decimal) for v in got.values()))
'''

FACTS = [
 'Сервис называется «Север».', 'Версия протокола — 2.4.',
 'Максимальный размер запроса — 8 МиБ.', 'Таймаут запроса — 30 секунд.',
 'Повторная отправка допускается не более 3 раз.', 'Ключ дедупликации хранится 24 часа.',
 'Архив хранится 14 дней.', 'Удаление архива запрещено.',
 'Режим dry-run не изменяет данные.', 'Проверка TLS обязательна.',
 'Секреты нельзя записывать в журнал.', 'Сбой проверки означает остановку.',
 'Время указывается в Europe/Moscow.', 'Владелец процедуры — platform-ops.',
 'Входной файл имеет формат NDJSON.', 'Пустые строки пропускаются.',
 'Первое событие с данным ID сохраняется.', 'Повторный ID не заменяет первое событие.',
 'Clients may retry temporary failures.', 'Clients must not disable TLS verification.',
]
FILLER = ('Этот пункт следует читать вместе с остальными условиями процедуры. '
          'Его формулировка повторяет сведения из рабочей карточки и не вводит дополнительных требований. '
          'В исходном описании вокруг этого условия есть несколько пояснений, которые можно сократить, '
          'сохранив смысл и связь с соседними действиями.')
HEADINGS = ['## Подготовка', '## Проверка входа', '## Пробный запуск',
            '## Выполнение', '## Проверка результата', '## Остановка']
COMMANDS = ['northctl validate input.ndjson', 'northctl run --dry-run input.ndjson',
            'northctl run input.ndjson', 'northctl verify receipt.json']


def put(base, name, text):
    p = base / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def build(root):
    f = root / 'fixtures'
    o = root / 'oracle'
    for task in ['go', 'python', 'edit', 'write', 'search']:
        (f / task).mkdir(parents=True, exist_ok=True)
    o.mkdir(exist_ok=True)
    common = ('Выполни это полностью утверждённое синтетическое задание без дополнительных вопросов. '
              'Разрешены только локальные исходники и встроенные инструменты. Не используй сеть, '
              'делегирование другим моделям, git commit/push, изменение глобальных настроек, '
              'получение credentials или создание work items. Эта копия принадлежит supervised benchmark runner '
              'в рамках задачи 34; никакие production операции не нужны. '
              'Работай только внутри текущего каталога. Заверши процесс после результата.\n\n')
    put(f/'go', 'go.mod', 'module synthetic/records\n\ngo 1.27\n')
    put(f/'go', 'records.go', GO_BROKEN)
    put(f/'go', 'records_test.go', GO_VISIBLE)
    put(o, 'acceptance_test.go', GO_HIDDEN)
    put(f/'go', 'TASK.md', common + '''Исправь records.go, не меняя публичный API ReadUnique(io.Reader, int) ([]Record, error).
Вход — NDJSON. Пропускай пустые строки. maxBytes > 0 ограничивает длину содержимого строки без CR/LF в байтах; проверь лимит даже на пустом потоке.
Поддержи допустимые строки больше 64 КиБ. Каждая непустая строка — JSON Record с непустым после TrimSpace ID; сам ID не нормализуй.
Сохраняй порядок появления и только первую запись каждого точного ID. Повторные записи тоже должны проходить синтаксическую проверку.
Любая ошибка JSON, ID, длины или io.Reader возвращает nil и ошибку; частичный результат запрещён. Ошибку чтения не теряй.
Не меняй существующие tests; можно добавлять свои. Только stdlib. Запусти go test ./... и оставь исправление в records.go.
''')
    put(f/'python', 'aggregate.py', PY_BROKEN)
    put(f/'python', 'test_visible.py', PY_VISIBLE)
    put(o, 'test_acceptance.py', PY_HIDDEN)
    put(f/'python', 'TASK.md', common + '''Исправь aggregate(text: str) -> dict[str, Decimal] в aggregate.py, только stdlib.
CSV имеет ровно столбцы id,currency,kind,amount (порядок допускается любой, дубликаты заголовков запрещены).
Пустой ввод или только заголовок -> {}. Пропускай пустые CSV-строки. У значений убери внешние пробелы.
id непустой. currency: только RUB, USD, EUR. kind: payment или refund.
amount — неотрицательная десятичная строка вида [0-9]+(?:\\.[0-9]+)?, без знака, exponent, NaN или Infinity.
Квантуй КАЖДУЮ строку до 0.01 с ROUND_HALF_UP через Decimal; payment прибавляется, refund вычитается. Нулевые суммы сохраняются.
Точный повтор ID с одинаковыми currency,kind и уже квантованной суммой учитывается один раз; конфликт повторного ID -> ValueError.
Любая неверная строка, число столбцов или заголовок -> ValueError. Возвращаемые значения всегда Decimal, float запрещён.
Существующие tests не меняй; можно добавлять свои. Запусти python3 -m unittest discover и оставь исправление в aggregate.py.
''')
    edit_source = '# Исходное описание\n\n' + '\n\n'.join(x+' '+FILLER for x in FACTS)
    put(f/'edit', 'source.md', edit_source+'\n')
    prose = {'min_words':450,'max_words':550,'protected':FACTS,'headings':[],
             'forbidden':['Удаление архива разрешено.', 'Проверка TLS необязательна.']}
    put(o, 'edit.json', json.dumps(prose,ensure_ascii=False,indent=2))
    put(f/'edit', 'TASK.md', common + '''Отредактируй source.md: создай result.md на русском, 450–550 слов (слова разделены whitespace).
Сократи повторы и канцелярит, сохрани технический регистр и условия. Все 20 фактических предложений, перечисленных ниже,
являются защищёнными фрагментами: сохрани каждое дословно, включая may и must not. Остальную прозу перепиши свободно.
Новые числа и новые требования не добавляй. source.md не меняй. Ответ в result.md, финальная реплика короткая.
\n'''+'\n'.join(FACTS)+'\n')
    write_spec = {'min_words':400,'max_words':600,'protected':FACTS+COMMANDS,'headings':HEADINGS,
                  'forbidden':prose['forbidden'],'command_sections':dict(zip(COMMANDS,HEADINGS[1:5]))}
    put(o, 'write.json', json.dumps(write_spec,ensure_ascii=False,indent=2))
    put(f/'write', 'facts.md', '# Карточка фактов\n\n'+'\n'.join(FACTS)+'\n\nКоманды в порядке выполнения:\n'+'\n'.join(COMMANDS)+'\n')
    put(f/'write', 'TASK.md', common + '''По facts.md напиши result.md: самостоятельную техническую инструкцию на русском, 400–600 слов (whitespace).
Аудитория — оператор, впервые выполняющий процедуру. Шесть разделов в заданном порядке:
'''+ '\n'.join(HEADINGS)+'''
Все 20 предложений карточки — защищённые фрагменты: включи каждое дословно. Команды тоже сохрани дословно и в порядке карточки.
validate относится к проверке входа, dry-run к пробному запуску, run к выполнению, verify к проверке результата.
Поясни переходы между шагами и условия остановки только из карточки. Не добавляй новые факты, команды, числа и требования.
facts.md не меняй. Финальная реплика короткая, вся инструкция в result.md.
''')
    current = ['# Актуальный регламент', 'status: active', 'revision: 2026-10-15',
               'Владелец: platform-ops.', 'Таймаут: 30 секунд.', 'Лимит запроса: 8 МиБ.',
               'Архив: 14 дней.', 'Ключ дедупликации: 24 часа.', 'Повторы: не более 3.',
               'Часовой пояс: Europe/Moscow.', 'Формат входа: NDJSON.',
               'Изменение данных в dry-run: запрещено.', 'Удаление архива: запрещено.',
               'Проверка TLS: обязательна.']
    docs = f/'search'/'docs'
    put(docs,'01-current.md','\n'.join(current)+'\n')
    old = ['# Архив', 'status: superseded', 'revision: 2025-01-01', 'Таймаут: 10 секунд.',
           'Лимит запроса: 2 МиБ.', 'Архив: 7 дней.', 'Проверка TLS: необязательна.']
    put(docs,'02-archive.md','\n'.join(old)+'\n')
    for i in range(3,31):
        lines = [f'# Справка {i:02}', 'status: background', 'Этот файл не заменяет актуальный регламент.']
        lines += [f'Запись {j:03}: справочный пример компонента section-{i:02}; обсуждение формата, процедуры, документации, наблюдений и ограничений. Эти сведения не задают действующие лимиты сервиса «Север».' for j in range(27)]
        put(docs,f'{i:02}-background.md','\n'.join(lines)+'\n')
    qs = [('Кто владелец?', 'platform-ops',4),('Каков таймаут в секундах?', '30',5),
          ('Каков лимит запроса в МиБ?', '8',6),('Сколько дней хранится архив?', '14',7),
          ('Сколько часов хранится ключ дедупликации?', '24',8),('Сколько допускается повторов?', '3',9),
          ('Какой часовой пояс?', 'Europe/Moscow',10),('Какой формат входа?', 'NDJSON',11),
          ('Разрешено ли изменение данных в dry-run?', 'запрещено',12),
          ('Разрешено ли удаление архива?', 'запрещено',13),
          ('Какой адрес электронной почты дежурного?', 'не найдено',None),
          ('Обязательна ли проверка TLS?', 'обязательна',14)]
    expected=[{'id':i,'answer':a,'evidence':[{'file':'docs/01-current.md','line':line}] if line else []}
              for i,(_,a,line) in enumerate(qs,1)]
    put(o,'search.json',json.dumps(expected,ensure_ascii=False,indent=2))
    put(f/'search','TASK.md',common+'''Найди ответы в docs/. Используй только действующий регламент; архив и background не задают актуальные значения.
Создай result.json — массив из 12 объектов в порядке вопросов: {"id":1,"answer":"строка","evidence":[{"file":"docs/01-current.md","line":4}]}.
answer должен содержать только запрошенное значение без единиц и пояснений; для да/нет используй «запрещено» или «обязательна» по смыслу.
Если данных нет, answer="не найдено", evidence=[]. Для найденного ответа приведи ровно одну строку источника, нумерация с 1.
Исходные документы не меняй. Финальная реплика короткая.
\n'''+ '\n'.join(f'{i}. {q}' for i,(q,_,_) in enumerate(qs,1))+'\n')
    return f,o


if __name__ == '__main__':
    build(Path(__file__).resolve().parent)
