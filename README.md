# 📝 Notes se Quiz

Notes paste karo, Gemini MCQ banata hai, aap solve karo, score aur explanation dekho,
galat sawalon ki practice karo, purane results history mein. Login ki zaroorat nahi.

## Folder structure (bilkul aisa hi rakhna)
```
quizmaker/
├── venv/                 ← Python environment (khud banta hai, isme kuch mat rakho)
├── app.py                ← poora backend
├── requirements.txt
├── .env                  ← aapki key (.env.example ka naam badal ke banao)
├── static/style.css
└── templates/            ← venv ke BAHAR, app.py ke bagal mein
    ├── base.html
    ├── index.html
    ├── quiz.html
    ├── result.html
    └── history.html
```

## Chalane ke steps (terminal `quizmaker` folder mein kholo)

**Windows**
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```
**Mac / Linux**
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

1. `.env.example` ka naam badal ke **`.env`** karo aur `GEMINI_API_KEY=` ke aage apni key paste karo.
   (Key: https://aistudio.google.com/apikey se free mil jati hai.)
2. Chalao: `python app.py`
3. Browser mein kholo: **http://127.0.0.1:5000**
   (HTML file ko seedha ya Live Server se mat kholna.)

**Key abhi nahi hai?** `.env` mein `DEMO_MODE=1` kar do. Nakli sawal aayenge, par poora app (quiz, score, history) chalke dekh sakte ho.

**Model error aaye?** `.env` mein `GEMINI_MODEL=` wahi naam rakho jo aapke Ask Baba project mein chalta hai.

## Ye app kaise kaam karta hai (study ke liye)
| Route | Kaam | Seekhne wali cheez |
|---|---|---|
| `GET /` | notes ka form dikhata hai | `render_template` |
| `POST /generate` | notes check karo, Gemini se sawal lo, DB mein save karo | `request.form`, validation, API call |
| `GET /quiz/<id>` | quiz dikhata hai | URL se `id` lena, DB se padhna |
| `POST /quiz/<id>/submit` | jawab check karke score nikalta hai, attempt save | grading logic, `INSERT` |
| `GET /result/<id>` | score, sahi/galat, explanation | Jinja `for`, `if` |
| `POST /result/<id>/practice` | galat sawalon ka naya quiz | list comprehension, `zip` |
| `GET /history` | purane results | `JOIN` query |

Zaroori functions `app.py` mein:
- `build_prompt()`: Gemini ko kya bolna hai (prompt likhna seekhne ki jagah).
- `parse_questions()`: Gemini ka jawab saaf karke check karta hai (galat format hata deta hai).
- `generate_questions()`: 2 baar try karta hai, fail ho to saaf error message.

## Practice (khud karo)
1. Result page par **time** dikhao: quiz kitni der mein solve hua.
2. History mein **average score** dikhao (`AVG(score*1.0/total)` SQL).
3. History mein har row ke saath **Delete** button banao (`DELETE FROM attempts WHERE id=?`).
4. Quiz page par ek **countdown timer** (JavaScript `setInterval`).
5. Notes ki jagah **PDF upload** karo (library: `pypdf`).
6. Quiz ko **login ke saath** jodo (Ask Baba ka system dekh ke).
