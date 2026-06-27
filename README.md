# Fitness & Health AI Dashboard

Fitness dashboard powered by RAG (Retrieval-Augmented Generation) with personalized workout and nutrition plans.

## 🎓 Project Info

- **University:** Tsinghua University
- **Course:** Web Information Retrieval
- **Stack:** Next.js 15 + React 19 + TypeScript + Tailwind CSS
- **Backend:** Python FastAPI + RAG + Elasticsearch k-NN + OpenAI GPT-4o-mini
- **Nutrition Science:** BMR/TDEE calculations (Mifflin-St Jeor equation)

## ✨ Features

- 🎯 **Personalized Fitness Plans** - AI-powered recommendations based on comprehensive user profile
- 📋 **Activity Level Support** - Tailored plans for sedentary to extra active lifestyles (5 levels)
- 🍽️ **Weekly Meal Planning** - Smart meal scheduling with portion options (0.5x, 1.0x, 1.5x, 2.0x)
- 🍿 **Snack Management** - Separate snack options to complement main meals
- 💪 **Workout Schedules** - Exercise routines with duration and muscle targeting
- 📊 **Macro Visualization** - Donut charts showing protein/carbs/fats distribution per recipe
- 📝 **Enumerated Recipes** - Step-by-step ingredients and instructions
- 🌙 **Dark Mode** - Beautiful glassmorphism UI with dark theme support
- 📱 **Responsive Design** - Works seamlessly on mobile, tablet, and desktop

## 🚀 Quick Start

### Installation
```bash
npm install
```

### Development
```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

### Build
```bash
npm run build
```

### Production
```bash
npm start
```

## 🔧 Configuration

Create `.env.local` file:
```
NEXT_PUBLIC_API_URL=https://tsinghua-workshop.onrender.com
```

Or for local development:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 📊 Dashboard Sections (v3.0)

### 1. Plan Summary Header
- Plan title and detected goal type
- User profile: age, sex, weight, height, BMI
- **NEW in v3:** Activity level, BMR, TDEE, activity factor
- **NEW in v3:** Goal type, calorie adjustment, safety flags

### 2. Weekly Calendar (7 Days)
- **Meals:** Grouped by meal_type (Breakfast, Lunch, Dinner, Morning/Afternoon/Evening Snack)
- **Workouts:** Exercise indices with focus area and duration
- **Daily Totals:** Recalculated calories, protein, carbs, fats
- **Notes:** AI-generated daily tips

### 3. Meal Options
- All available meals from backend (20-25 options)
- **🆕 Donut Charts:** Visual macro distribution (Protein/Carbs/Fats)
- **🆕 Enumerated Lists:**
  - Ingredients (numbered list)
  - Instructions (numbered steps)
- **Portion Options:** 4 multipliers with calculated macros

### 4. Snack Options
- Separate snack library (8-10 options)
- Same features as meal options (donut charts, enumerated lists)
- Orange color scheme (vs. purple for meals)

### 5. Workout Options
- Exercise name, target muscle, equipment
- MET score
- Expandable instructions

### 6. AI Recommendations
- Main tip
- Personalized notes (activity level + goal)
- Nutrition tips (macro distribution, meal timing)
- Workout tips (frequency, recovery)
- **Safety notes** (from backend validation)

### 7. Retrieval Evidence
- Recipes retrieved, meal options available, snack options available
- Exercises used
- Data source info
- Validation method (python_recalculated)

## 🎨 UI/UX Features

### 🍩 Donut Charts (Macro Distribution)
Each recipe card shows a CSS-based donut chart:
- **Blue segment:** Protein
- **Green segment:** Carbs
- **Orange segment:** Fats
- Percentages calculated from base macros

### 📋 Enumerated Lists
- **Ingredients:** Ordered list with decimal numbering
- **Instructions:** Steps split by periods and numbered

### 📱 Responsive Grid
- **Mobile:** 1 column
- **Tablet:** 2 columns
- **Desktop:** 2-3 columns depending on section

## 🔄 How It Works

### User Input Form
The form collects:
- **Age** (years)
- **Sex** (Male/Female dropdown)
- **Weight** (kg)
- **Height** (cm)
- **🆕 Activity Level** (5-option dropdown):
  - Sedentary (little/no exercise)
  - Lightly Active (1-3 days/week)
  - Moderately Active (3-5 days/week)
  - Very Active (6-7 days/week)
  - Extra Active (physical job + training)
- **Fitness Goal** (free text: lose weight, gain muscle, maintain, etc.)

### Backend Processing
1. **BMR Calculation** - Basal Metabolic Rate using Mifflin-St Jeor equation
2. **TDEE Calculation** - Total Daily Energy Expenditure (BMR × activity factor)
3. **Goal Classification** - Detects weight loss (-20%), muscle gain (+15%), recomp (-10%), or maintenance (0%)
4. **Safety Checks** - Prevents unsafe calorie deficits/surpluses (min 1200/1500 kcal, max ±25% TDEE)
5. **RAG Retrieval** - Elasticsearch k-NN search for recipes (30 main + 15 snacks) & exercises (12)
6. **LLM Personalization** - OpenAI GPT-4o-mini generates 7-day plan with portion multipliers
7. **Python Validation** - Recalculates and validates all macros, ensures targets met

### Frontend Display
Dashboard dynamically renders 7 sections based on backend response structure.

## 📁 Project Structure

```
fitness-dashboard/
├── app/
│   ├── components/      # Empty (ready for future components)
│   ├── page.tsx         # 🔥 MAIN DASHBOARD (all functionality)
│   ├── layout.tsx       # Root layout with metadata
│   └── globals.css      # Global styles + donut chart CSS
├── public/              # Static assets
├── .env.local           # Environment variables (create this)
├── package.json         # Dependencies
└── README.md            # This file
```

## 🧪 Testing

1. **Start backend API:**
```bash
python main.py  # or uvicorn main:app --reload
```

2. **Start frontend:**
```bash
npm run dev
```

3. **Fill form with test data:**
   - Age: 25
   - Sex: Male
   - Weight: 75 kg
   - Height: 175 cm
   - Activity Level: Moderately Active
   - Goal: "I want to gain muscle and lose fat"

4. **Verify:**
   - ✅ Plan generates successfully
   - ✅ Donut charts appear on recipe cards
   - ✅ Ingredients/instructions are numbered
   - ✅ Weekly calendar shows meals by type
   - ✅ Snacks section appears separately
   - ✅ User profile shows BMR, TDEE, activity level

## 🛠️ Available Scripts

- `npm run dev` - Start development server (port 3000)
- `npm run build` - Build for production
- `npm start` - Start production server
- `npm run lint` - Run ESLint

## 🔧 Git Commands

Use the included `git-push.bat` script:
```bash
git-push.bat
```

Or manually:
```bash
git add .
git commit -m "your message"
git push origin main
```

## 📝 Recent Changes (v3.0 - June 2026)

- ✅ **Removed** Daily Targets section from user profile
- ✅ **Removed** Macro Overview section with progress bars
- ✅ **Added** activity_level dropdown to form (5 options)
- ✅ **Added** donut charts to every recipe card (meals + snacks)
- ✅ **Added** enumerated ingredients and instructions
- ✅ **Updated** user profile to show BMR, TDEE, activity_level, goal_type
- ✅ **Separated** snacks into dedicated section (section 4)
- ✅ **Updated** weekly calendar to use meal_type structure
- ✅ **Cleaned** project structure (removed 30+ unnecessary files)

## 🎨 Design System

- **Glassmorphism** effects with backdrop blur
- **Gradient backgrounds** for visual hierarchy
- **Dark mode** fully supported with system preference detection
- **Color scheme:**
  - Purple/Indigo for meals
  - Orange/Red for snacks
  - Blue for workouts
  - Amber/Orange for AI tips
  - Gray/White for base UI

## 🤝 Contributing

This is a Tsinghua University workshop project. Feel free to fork and modify!

## 📄 License

MIT

## 🔗 Repository

https://github.com/MichelleArceo/Tsinghua_Workshop_Frontend

## 👥 Team

Tsinghua University - Web Information Retrieval Course
