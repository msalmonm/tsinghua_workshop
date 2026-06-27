"use client";

import { useState, useEffect } from "react";
import { jsPDF } from "jspdf";

// Staged progress phases shown while the plan is generating (~1 min total)
const LOADING_STAGES = [
  { label: "Analyzing your profile and goals", pct: 12, ms: 6000 },
  { label: "Calculating calories and macro targets", pct: 28, ms: 8000 },
  { label: "Retrieving the best recipes for you", pct: 50, ms: 14000 },
  { label: "Selecting and balancing your exercises", pct: 68, ms: 12000 },
  { label: "Generating your personalized plan", pct: 88, ms: 16000 },
  { label: "Finalizing and balancing your week", pct: 97, ms: 8000 },
];

// Activity level options with clear real-world benchmarks
const ACTIVITY_OPTIONS = [
  { value: "sedentary", label: "Sedentary", benchmark: "No regular exercise, mostly sitting. Fewer than 2,000–3,000 steps/day." },
  { value: "lightly_active", label: "Lightly Active", benchmark: "Light walking or light exercise 1–2 days/week. ~3,000–6,000 steps/day." },
  { value: "moderately_active", label: "Moderately Active", benchmark: "Exercise 3–4 days/week. ~6,000–10,000 steps/day." },
  { value: "very_active", label: "Very Active", benchmark: "Intense exercise 5–6 days/week. 10,000+ steps/day." },
  { value: "extremely_active", label: "Athlete / Extremely Active", benchmark: "High-intensity training or physical job. Daily or multiple sessions per day." },
];

// Resolve the correct original-recipe URL (fixes the homepage redirect bug)
const resolveRecipeUrl = (recipe: MealOption): string | null => {
  if (recipe.recipe_url && recipe.recipe_url.startsWith("http")) return recipe.recipe_url;
  if (recipe.recipe_id?.startsWith("rec_fs_")) {
    const id = recipe.recipe_id.replace("rec_fs_", "");
    return `https://www.fatsecret.com/recipes/${id}/`;
  }
  if (recipe.recipe_id?.startsWith("rec_mealdb_")) {
    const id = recipe.recipe_id.replace("rec_mealdb_", "");
    return `https://www.themealdb.com/meal/${id}`;
  }
  return null;
};

// Helper functions for UI components
const getMETColor = (met: number) => {
  if (met < 3) return "text-green-600 dark:text-green-400";
  if (met >= 3 && met <= 6) return "text-yellow-600 dark:text-yellow-400";
  return "text-red-600 dark:text-red-400";
};

const getBMICategory = (bmi: number) => {
  if (bmi < 18.5) return { category: "Underweight", color: "text-blue-600 dark:text-blue-400" };
  if (bmi >= 18.5 && bmi <= 24.9) return { category: "Healthy Weight", color: "text-green-600 dark:text-green-400" };
  if (bmi >= 25.0 && bmi <= 29.9) return { category: "Overweight", color: "text-yellow-600 dark:text-yellow-400" };
  return { category: "Obese", color: "text-red-600 dark:text-red-400" };
};

const formatInstructions = (instructions: string): string[] => {
  if (!instructions) return [];
  
  const steps = instructions
    .split(/(?:\d+\.\s*|\n|\.\s*(?=[A-Z])|;\s*(?=[A-Z]))/)
    .map(step => step.trim())
    .filter(step => step.length > 10)
    .slice(0, 10);
  
  return steps;
};

// With the unified backend catalog, recipe_indices point directly into plan.meal_options.
const getCatalog = (plan: PlanData): MealOption[] => plan.meal_options || [];

// Combine the recipes of a single meal entry (a meal may have 1-3 recipes)
const resolveMealRecipes = (
  meal: MealEntry,
  catalog: MealOption[]
): Array<{ recipe: MealOption; multiplier: number }> => {
  if (!meal) return [];
  return meal.recipe_indices
    .map((idx, i) => ({
      recipe: catalog[idx],
      multiplier: meal.portion_multipliers?.[i] ?? 1.0,
    }))
    .filter((m) => !!m.recipe);
};

// Scale a recipe's macros by a portion multiplier
const scaled = (value: number, multiplier: number) => Math.round(value * multiplier);

// Donut chart SVG component
const DonutChart = ({ calories, protein, carbs, fats, compact = false }: { 
  calories: number;
  protein: number; 
  carbs: number; 
  fats: number;
  compact?: boolean;
}) => {
  const total = protein + carbs + fats;
  if (total === 0) return null;

  const proteinPct = (protein / total) * 100;
  const carbsPct = (carbs / total) * 100;
  const fatsPct = (fats / total) * 100;

  const size = compact ? 80 : 130;
  const radius = compact ? 30 : 50;
  const strokeWidth = compact ? 12 : 18;

  // Calculate stroke-dasharray for donut segments
  const circumference = 2 * Math.PI * radius;
  const proteinDash = (proteinPct / 100) * circumference;
  const carbsDash = (carbsPct / 100) * circumference;
  const fatsDash = (fatsPct / 100) * circumference;

  return (
    <div className="relative flex items-center justify-center">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="transform -rotate-90">
        {/* Protein segment */}
        <circle
          cx={size/2}
          cy={size/2}
          r={radius}
          fill="none"
          stroke="#7c3aed"
          strokeWidth={strokeWidth}
          strokeDasharray={`${proteinDash} ${circumference}`}
          strokeDashoffset="0"
        />
        {/* Carbs segment */}
        <circle
          cx={size/2}
          cy={size/2}
          r={radius}
          fill="none"
          stroke="#3b82f6"
          strokeWidth={strokeWidth}
          strokeDasharray={`${carbsDash} ${circumference}`}
          strokeDashoffset={`-${proteinDash}`}
        />
        {/* Fats segment */}
        <circle
          cx={size/2}
          cy={size/2}
          r={radius}
          fill="none"
          stroke="#f97316"
          strokeWidth={strokeWidth}
          strokeDasharray={`${fatsDash} ${circumference}`}
          strokeDashoffset={`-${proteinDash + carbsDash}`}
        />
      </svg>
      {/* Center calories display */}
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        <div className={`font-bold text-gray-900 dark:text-gray-100 ${compact ? 'text-lg' : 'text-xl'}`}>
          {calories}
        </div>
        <div className={`text-gray-600 dark:text-gray-400 ${compact ? 'text-xs' : 'text-sm'}`}>
          kcal
        </div>
      </div>
    </div>
  );
};

// API response interfaces
interface PlanData {
  plan_summary: {
    title: string;
    goal_detected: string;
    short_summary: string;
    focus: string;
    difficulty_level: string;
    training_frequency_per_week?: number;
    target_body_parts?: string[];
    days_generated?: number;
  };
  intent?: {
    fitness_goal: string;
    target_body_parts: string[];
    training_frequency_per_week: number;
    nutrition_goal: string;
    dietary_restrictions: string[];
    num_days: number;
    wants_weekly_plan: boolean;
    meal_prep_style: boolean;
  };
  user_profile_summary: {
    age: number;
    sex: string;
    weight_kg: number;
    height_cm: number;
    bmi: number;
    activity_level: string;
    bmr?: number;
    tdee?: number;
  };
  nutrition_summary: {
    avg_daily_calories: number;
    avg_daily_protein_g: number;
    avg_daily_carbs_g: number;
    avg_daily_fats_g: number;
  };
  macro_bars: Array<{
    label: string;
    value: number;
    unit: string;
  }>;
  weekly_balance?: {
    balanced: boolean;
    spreads: Record<string, number>;
  };
  meal_options: MealOption[];
  snack_options: MealOption[];
  workout_options: WorkoutOption[];
  weekly_calendar: WeeklyDay[];
  ai_recommendations: {
    main_tip: string;
    personalized_notes: string[];
    nutrition_tips: string[];
    workout_tips: string[];
    safety_notes: string[];
  };
}

interface PortionOption {
  multiplier: number;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fats_g: number;
}

interface MealOption {
  recipe_id: string;
  recipe_name: string;
  ready_in_minutes: number;
  ingredient_count?: number;
  diet_tags: string[];
  base_calories: number;
  base_protein_g: number;
  base_carbs_g: number;
  base_fats_g: number;
  snack_friendly?: boolean;
  meal_hint?: string;
  portion_options: PortionOption[];
  ingredients: string;
  instructions: string;
  recipe_image?: string;
  recipe_url?: string;
}

interface WorkoutOption {
  exercise_id: string;
  name: string;
  target_muscle: string;
  equipment: string;
  estimated_met: number;
  instructions: string;
}

interface MealEntry {
  meal_type: string;
  recipe_indices: number[];
  portion_multipliers: number[];
}

interface WeeklyDay {
  day: string;
  is_rest_day?: boolean;
  meals: MealEntry[];
  daily_totals: {
    calories: number;
    protein_g: number;
    carbs_g: number;
    fats_g: number;
  };
  workout: {
    exercise_indices: number[];
    focus: string;
    duration_min: number;
    cardio_min?: number;
    cardio_note?: string;
  };
  notes: string;
}

interface ResultData {
  response: string;
  plan: PlanData;
}

export default function Dashboard() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ResultData | null>(null);
  const [error, setError] = useState("");
  const [selectedDay, setSelectedDay] = useState(0);
  const [showRecipeModal, setShowRecipeModal] = useState<MealOption | null>(null);
  const [showExerciseModal, setShowExerciseModal] = useState<WorkoutOption | null>(null);
  const [showAllRecommendations, setShowAllRecommendations] = useState(false);
  const [coachQuery, setCoachQuery] = useState("I want a leg hypertrophy routine and a high-protein diet.");
  const [formData, setFormData] = useState({
    age: 24,
    sex: "Male",
    weight_kg: 75,
    height_cm: 175,
    activity_level: "moderately_active",
    query: "I want a leg hypertrophy routine and a high-protein diet.",
  });
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [exporting, setExporting] = useState(false);
  const [stageIndex, setStageIndex] = useState(0);
  const [progress, setProgress] = useState(0);

  // Drive the staged loading progress while waiting for the backend (~1 min).
  // Progress eases toward each stage's target and creeps between checkpoints
  // so the bar never stalls; it resets when loading ends.
  useEffect(() => {
    if (!loading) {
      setStageIndex(0);
      setProgress(0);
      return;
    }
    let cancelled = false;
    const timers: ReturnType<typeof setTimeout>[] = [];
    let elapsed = 0;
    LOADING_STAGES.forEach((stage, i) => {
      const t = setTimeout(() => {
        if (cancelled) return;
        setStageIndex(i);
        setProgress(stage.pct);
      }, elapsed);
      timers.push(t);
      elapsed += stage.ms;
    });
    const creep = setInterval(() => {
      if (cancelled) return;
      setProgress((p) => (p < 97 ? Math.min(p + 0.4, 97) : p));
    }, 400);
    return () => {
      cancelled = true;
      timers.forEach(clearTimeout);
      clearInterval(creep);
    };
  }, [loading]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    setFieldErrors((prev) => ({ ...prev, [e.target.name]: "" }));
  };

  // Client-side guardrails for unrealistic / wrongly formatted inputs
  const validateProfile = (): Record<string, string> => {
    const errors: Record<string, string> = {};
    const age = Number(formData.age);
    const weight = Number(formData.weight_kg);
    const height = Number(formData.height_cm);

    if (formData.age === null || formData.age === undefined || String(formData.age).trim() === "") {
      errors.age = "Age is required.";
    } else if (!Number.isFinite(age) || age <= 0) {
      errors.age = "Age must be a positive number.";
    } else if (age < 13 || age > 100) {
      errors.age = "Please enter a realistic age between 13 and 100.";
    }

    if (String(formData.height_cm).trim() === "") {
      errors.height_cm = "Height is required.";
    } else if (!Number.isFinite(height) || height <= 0) {
      errors.height_cm = "Height must be a positive number.";
    } else if (height < 90) {
      errors.height_cm = "Please enter your height in centimeters, for example 180 instead of 1.8.";
    } else if (height > 250) {
      errors.height_cm = "Please enter a realistic height in centimeters (90–250 cm).";
    }

    if (String(formData.weight_kg).trim() === "") {
      errors.weight_kg = "Weight is required.";
    } else if (!Number.isFinite(weight) || weight <= 0) {
      errors.weight_kg = "Weight must be a positive number.";
    } else if (weight < 25 || weight > 400) {
      errors.weight_kg = "Please enter a realistic weight in kilograms (25–400 kg).";
    }

    if (!coachQuery || !coachQuery.trim()) {
      errors.query = "Please describe what you want to achieve.";
    }
    return errors;
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    const errors = validateProfile();
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      setError("Please correct the highlighted fields before generating your plan.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);
    setSelectedDay(0);

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: coachQuery,
          user_profile: {
            age: Number(formData.age),
            sex: formData.sex,
            weight_kg: Number(formData.weight_kg),
            height_cm: Number(formData.height_cm),
            activity_level: formData.activity_level,
          },
        }),
      });

      if (!res.ok) {
        let message = "Backend connection error";
        try {
          const errBody = await res.json();
          if (errBody?.detail) {
            message = Array.isArray(errBody.detail)
              ? errBody.detail.map((d: any) => d.msg || d).join(" ")
              : errBody.detail;
          }
        } catch {
          /* ignore parse errors */
        }
        throw new Error(message);
      }
      const data = await res.json();
      setProgress(100);
      setResult(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Get day name for nutrition summary
  const getDayName = () => {
    if (!result?.plan?.weekly_calendar) return "Today";
    const cal = result.plan.weekly_calendar;
    return cal[selectedDay]?.day || "Today";
  };

  // ---------- PDF EXPORT ----------
  // Page 1: profile + goals + plan summary. Then one page per generated day
  // with recipe cards and an exercise table. Visually organized.
  const handleExportPDF = () => {
    if (!result?.plan) return;
    setExporting(true);
    try {
      const plan = result.plan;
      const catalog = getCatalog(plan);
      const doc = new jsPDF({ unit: "pt", format: "a4" });
      const pageW = doc.internal.pageSize.getWidth();
      const pageH = doc.internal.pageSize.getHeight();
      const margin = 40;
      const maxW = pageW - margin * 2;
      let y = margin;

      // palette
      const PURPLE: [number, number, number] = [124, 58, 237];
      const INK: [number, number, number] = [33, 33, 40];
      const MUTED: [number, number, number] = [120, 120, 130];
      const LINE: [number, number, number] = [228, 228, 235];

      const ensureSpace = (needed: number) => {
        if (y + needed > pageH - margin) {
          doc.addPage();
          y = margin;
        }
      };

      const text = (
        s: string,
        x: number,
        size = 10,
        style: "normal" | "bold" = "normal",
        color: [number, number, number] = INK
      ) => {
        doc.setFont("helvetica", style);
        doc.setFontSize(size);
        doc.setTextColor(...color);
        doc.text(s, x, y);
      };

      const para = (
        s: string,
        size = 10,
        style: "normal" | "bold" = "normal",
        color: [number, number, number] = INK,
        indent = 0,
        lh = 4
      ) => {
        if (!s) return;
        doc.setFont("helvetica", style);
        doc.setFontSize(size);
        doc.setTextColor(...color);
        const lines = doc.splitTextToSize(s, maxW - indent);
        lines.forEach((line: string) => {
          ensureSpace(size + lh);
          doc.text(line, margin + indent, y);
          y += size + lh;
        });
      };

      const sectionTitle = (label: string) => {
        ensureSpace(26);
        y += 8;
        doc.setFillColor(...PURPLE);
        doc.roundedRect(margin, y - 11, maxW, 20, 3, 3, "F");
        doc.setFont("helvetica", "bold");
        doc.setFontSize(11);
        doc.setTextColor(255, 255, 255);
        doc.text(label, margin + 8, y + 3);
        y += 22;
      };

      // Coloured macro chips row (wraps to a new line if they exceed width)
      const macroChips = (
        x: number,
        chips: Array<{ label: string; value: string; rgb: [number, number, number] }>
      ) => {
        const h = 16;
        ensureSpace(h + 4);
        let cx = x;
        chips.forEach((c) => {
          doc.setFont("helvetica", "bold");
          doc.setFontSize(8);
          const w = doc.getTextWidth(`${c.label} ${c.value}`) + 16;
          if (cx + w > pageW - margin) {
            // wrap to next line
            cx = x;
            y += h + 4;
            ensureSpace(h + 4);
          }
          doc.setFillColor(c.rgb[0], c.rgb[1], c.rgb[2]);
          doc.roundedRect(cx, y - 11, w, h, 3, 3, "F");
          doc.setTextColor(255, 255, 255);
          doc.text(`${c.label} ${c.value}`, cx + 8, y);
          cx += w + 6;
        });
        y += h + 4;
      };

      // Count wrapped lines for a piece of text (used to pre-measure cards)
      const CARD_LH = 11;
      const wrappedCount = (s: string, size: number, indent: number) => {
        if (!s) return 0;
        doc.setFont("helvetica", "normal");
        doc.setFontSize(size);
        return doc.splitTextToSize(String(s), maxW - indent).length;
      };

      // Pre-measure the full height a recipe card will occupy.
      const measureCard = (recipe: MealOption) => {
        let h = 4 + 18 + 20; // top gap + header + macro chips
        if (recipe.ingredients) {
          h += CARD_LH; // "Ingredients" label
          h += wrappedCount(recipe.ingredients, 8, 10) * CARD_LH;
        }
        const steps = formatInstructions(recipe.instructions);
        if (steps.length > 0) {
          h += CARD_LH; // "Instructions" label
          steps.forEach((s, i) => {
            h += wrappedCount(`${i + 1}. ${s}`, 8, 14) * CARD_LH;
          });
        } else if (recipe.instructions) {
          h += wrappedCount(recipe.instructions, 8, 10) * CARD_LH;
        }
        return h + 14; // bottom padding
      };

      // A recipe card: title bar, macro chips, ingredients, instructions.
      // Pre-measures so the card never straddles a page, and only draws the
      // border when the whole card lives on one page (prevents overlap bugs).
      const recipeCard = (recipeName: string, multiplier: number, recipe: MealOption) => {
        const cal = scaled(recipe.base_calories, multiplier);
        const pro = scaled(recipe.base_protein_g, multiplier);
        const carb = scaled(recipe.base_carbs_g, multiplier);
        const fat = scaled(recipe.base_fats_g, multiplier);

        const needed = measureCard(recipe);
        const pageBudget = pageH - margin * 2;
        // If it fits on a fresh page but not here, break first so it's whole.
        if (y + needed > pageH - margin && needed <= pageBudget) {
          doc.addPage();
          y = margin;
        }

        const cardTop = y - 4;
        const startPage = doc.getNumberOfPages();

        // header
        doc.setFont("helvetica", "bold");
        doc.setFontSize(11);
        doc.setTextColor(...INK);
        const title = multiplier !== 1 ? `${recipeName}  (x${multiplier})` : recipeName;
        doc.text(doc.splitTextToSize(title, maxW - 90)[0], margin + 10, y + 6);
        doc.setFont("helvetica", "normal");
        doc.setFontSize(8);
        doc.setTextColor(...MUTED);
        doc.text(`${recipe.ready_in_minutes || "-"} min`, pageW - margin - 10, y + 6, { align: "right" });
        y += 18;

        macroChips(margin + 10, [
          { label: "KCAL", value: `${cal}`, rgb: [124, 58, 237] },
          { label: "P", value: `${pro}g`, rgb: [37, 99, 235] },
          { label: "C", value: `${carb}g`, rgb: [22, 163, 74] },
          { label: "F", value: `${fat}g`, rgb: [234, 88, 12] },
        ]);

        if (recipe.ingredients) {
          para("Ingredients", 8, "bold", MUTED, 10, 3);
          para(recipe.ingredients, 8, "normal", INK, 10, 3);
        }
        const steps = formatInstructions(recipe.instructions);
        if (steps.length > 0) {
          para("Instructions", 8, "bold", MUTED, 10, 3);
          steps.forEach((s, i) => para(`${i + 1}. ${s}`, 8, "normal", INK, 14, 3));
        } else if (recipe.instructions) {
          para(recipe.instructions, 8, "normal", INK, 10, 3);
        }

        // Only draw the border if the card stayed on one page.
        if (doc.getNumberOfPages() === startPage) {
          doc.setDrawColor(...LINE);
          doc.roundedRect(margin, cardTop, maxW, y - cardTop + 4, 4, 4, "S");
        }
        y += 14;
      };

      // Exercise table with header redrawn on every page and no row straddling.
      const exerciseTable = (rows: Array<WorkoutOption>) => {
        const cols = [
          { k: "#", w: 22 },
          { k: "Exercise", w: 150 },
          { k: "Target", w: 90 },
          { k: "Sets x Reps", w: 70 },
          { k: "Rest", w: 50 },
          { k: "MET", w: 35 },
          { k: "Equipment", w: maxW - 22 - 150 - 90 - 70 - 50 - 35 },
        ];
        const headerH = 18;

        const drawHeader = () => {
          doc.setFillColor(...PURPLE);
          doc.rect(margin, y, maxW, headerH, "F");
          doc.setFont("helvetica", "bold");
          doc.setFontSize(8);
          doc.setTextColor(255, 255, 255);
          let cx = margin;
          cols.forEach((c) => {
            doc.text(c.k, cx + 4, y + 12);
            cx += c.w;
          });
          y += headerH;
        };

        // Ensure room for header + at least one row before starting.
        ensureSpace(headerH + 22);
        drawHeader();

        rows.forEach((ex, i) => {
          doc.setFont("helvetica", "normal");
          doc.setFontSize(8);
          const nameLines = doc.splitTextToSize(ex.name, cols[1].w - 6);
          const rowH = Math.max(18, nameLines.length * 10 + 8);

          // Row must never straddle a page: break first, then redraw header.
          if (y + rowH > pageH - margin) {
            doc.addPage();
            y = margin;
            drawHeader();
          }

          if (i % 2 === 0) {
            doc.setFillColor(245, 244, 250);
            doc.rect(margin, y, maxW, rowH, "F");
          }

          const cells = [
            `${i + 1}`,
            ex.name,
            ex.target_muscle,
            "4 x 10-12",
            "60-90s",
            `${ex.estimated_met ?? "-"}`,
            ex.equipment,
          ];
          let cx = margin;
          cells.forEach((val, ci) => {
            doc.setTextColor(...(ci === 1 ? INK : MUTED));
            doc.setFont("helvetica", ci === 1 ? "bold" : "normal");
            doc.setFontSize(8);
            const lines = doc.splitTextToSize(String(val), cols[ci].w - 6);
            lines.forEach((ln: string, li: number) => {
              doc.text(ln, cx + 4, y + 12 + li * 10);
            });
            cx += cols[ci].w;
          });
          y += rowH;
        });

        doc.setDrawColor(...LINE);
        doc.line(margin, y, pageW - margin, y);
        y += 10;
      };

      // ---------- PAGE 1: PROFILE, GOALS, SUMMARY ----------
      doc.setFillColor(...PURPLE);
      doc.rect(0, 0, pageW, 72, "F");
      doc.setFont("helvetica", "bold");
      doc.setFontSize(20);
      doc.setTextColor(255, 255, 255);
      doc.text("AI Health Assistant", margin, 38);
      doc.setFont("helvetica", "normal");
      doc.setFontSize(11);
      doc.text("Your personalized fitness & nutrition plan", margin, 56);
      y = 100;

      para(plan.plan_summary?.title || "Fitness & Nutrition Plan", 16, "bold", PURPLE, 0, 6);

      const up = plan.user_profile_summary;
      sectionTitle("User Profile");
      para(`Age: ${up.age} years     Sex: ${up.sex}     Weight: ${up.weight_kg} kg     Height: ${up.height_cm} cm`, 10);
      para(`BMI: ${up.bmi.toFixed(1)} (${getBMICategory(up.bmi).category})     Activity: ${up.activity_level.replace(/_/g, " ")}`, 10);
      if (up.bmr && up.tdee) para(`BMR: ${Math.round(up.bmr)} kcal     TDEE: ${up.tdee} kcal`, 10);

      sectionTitle("Goals");
      para(`"${coachQuery}"`, 10, "normal", MUTED);
      if (plan.plan_summary?.goal_detected) para(`Detected goal: ${plan.plan_summary.goal_detected}`, 10);
      if (plan.plan_summary?.focus) para(`Training focus: ${plan.plan_summary.focus}`, 10);
      if (plan.plan_summary?.training_frequency_per_week)
        para(`Training frequency: ${plan.plan_summary.training_frequency_per_week} day(s)/week`, 10);
      para(`Difficulty: ${plan.plan_summary?.difficulty_level || "-"}     Days: ${plan.weekly_calendar.length}`, 10);

      sectionTitle("Plan Summary");
      para(plan.plan_summary?.short_summary || "", 10);
      const ns = plan.nutrition_summary;
      y += 2;
      macroChips(margin, [
        { label: "KCAL/day", value: `${Math.round(ns.avg_daily_calories)}`, rgb: [124, 58, 237] },
        { label: "Protein", value: `${Math.round(ns.avg_daily_protein_g)}g`, rgb: [37, 99, 235] },
        { label: "Carbs", value: `${Math.round(ns.avg_daily_carbs_g)}g`, rgb: [22, 163, 74] },
        { label: "Fats", value: `${Math.round(ns.avg_daily_fats_g)}g`, rgb: [234, 88, 12] },
      ]);
      if (plan.ai_recommendations?.main_tip) {
        para("Main recommendation", 9, "bold", MUTED);
        para(plan.ai_recommendations.main_tip, 10);
      }
      if (plan.ai_recommendations?.safety_notes?.length) {
        y += 2;
        para("Safety notes", 9, "bold", [200, 80, 0]);
        plan.ai_recommendations.safety_notes.forEach((n) => para(`- ${n}`, 9, "normal", [150, 90, 0], 6));
      }

      // ---------- ONE PAGE PER DAY ----------
      plan.weekly_calendar.forEach((day) => {
        doc.addPage();
        y = margin;
        doc.setFillColor(...PURPLE);
        doc.rect(0, 0, pageW, 52, "F");
        doc.setFont("helvetica", "bold");
        doc.setFontSize(16);
        doc.setTextColor(255, 255, 255);
        doc.text(`${day.day}${day.is_rest_day ? "  -  Rest Day" : ""}`, margin, 33);
        y = 76;

        const dt = day.daily_totals;
        macroChips(margin, [
          { label: "KCAL", value: `${dt.calories}`, rgb: [124, 58, 237] },
          { label: "P", value: `${dt.protein_g}g`, rgb: [37, 99, 235] },
          { label: "C", value: `${dt.carbs_g}g`, rgb: [22, 163, 74] },
          { label: "F", value: `${dt.fats_g}g`, rgb: [234, 88, 12] },
        ]);
        if (day.notes) para(day.notes, 9, "normal", MUTED);

        // Meals
        sectionTitle("Meals");
        day.meals.forEach((meal) => {
          const items = resolveMealRecipes(meal, catalog);
          if (items.length === 0) return;
          para(meal.meal_type, 10, "bold", PURPLE);
          items.forEach(({ recipe, multiplier }) => recipeCard(recipe.recipe_name, multiplier, recipe));
        });

        // Workout
        sectionTitle(day.is_rest_day ? "Recovery" : `Workout - ${day.workout?.focus || ""}`);
        if (day.is_rest_day || !day.workout?.exercise_indices?.length) {
          para("Rest / active recovery day. Light walking, stretching, or mobility work.", 10);
          if (day.workout?.cardio_min)
            para(`Cardio: ${day.workout.cardio_note || `${day.workout.cardio_min} min light cardio`}`, 9, "normal", [40, 90, 160], 6);
        } else {
          para(`Focus: ${day.workout.focus}     Duration: ${day.workout.duration_min} min`, 10, "bold");
          const rows = day.workout.exercise_indices
            .map((idx) => plan.workout_options[idx])
            .filter(Boolean) as WorkoutOption[];
          exerciseTable(rows);
          if (day.workout.cardio_min) {
            para(`Cardio finisher (${day.workout.cardio_min} min): ${day.workout.cardio_note || ""}`, 9, "bold", [40, 90, 160], 6);
          }
        }
      });

      const safeName = (plan.plan_summary?.title || "fitness-plan").replace(/[^a-z0-9]+/gi, "_").toLowerCase();
      doc.save(`${safeName}.pdf`);
    } catch (e: any) {
      setError(`Export failed: ${e?.message || "unknown error"}`);
    } finally {
      setExporting(false);
    }
  };

  // Recipe Modal Component
  const RecipeModal = ({ recipe, onClose }: { recipe: MealOption; onClose: () => void }) => {
    const formattedInstructions = formatInstructions(recipe.instructions);
    
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
        <div className="bg-white dark:bg-gray-800 rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
          <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">{recipe.recipe_name}</h2>
            <button onClick={onClose} className="text-gray-500 hover:text-gray-700">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="p-6 space-y-4">
            {/* Recipe Image: shown ONLY inside this modal, and ONLY when one exists */}
            {recipe.recipe_image && (
              <div className="rounded-lg overflow-hidden mb-4">
                <img
                  src={recipe.recipe_image}
                  alt={recipe.recipe_name}
                  className="w-full h-48 object-cover bg-purple-50 dark:bg-purple-900/20"
                  onError={(e) => {
                    // If the image fails to load, hide it (no placeholder).
                    const wrap = (e.target as HTMLImageElement).parentElement;
                    if (wrap) wrap.style.display = "none";
                  }}
                />
              </div>
            )}
            <div className="grid grid-cols-4 gap-4 text-center">
              <div className="p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
                <div className="text-lg font-bold text-purple-600 dark:text-purple-400">{recipe.base_calories}</div>
                <div className="text-xs text-gray-600 dark:text-gray-400">Calories</div>
              </div>
              <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                <div className="text-lg font-bold text-blue-600 dark:text-blue-400">{recipe.base_protein_g}g</div>
                <div className="text-xs text-gray-600 dark:text-gray-400">Protein</div>
              </div>
              <div className="p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
                <div className="text-lg font-bold text-green-600 dark:text-green-400">{recipe.base_carbs_g}g</div>
                <div className="text-xs text-gray-600 dark:text-gray-400">Carbs</div>
              </div>
              <div className="p-3 bg-orange-50 dark:bg-orange-900/20 rounded-lg">
                <div className="text-lg font-bold text-orange-600 dark:text-orange-400">{recipe.base_fats_g}g</div>
                <div className="text-xs text-gray-600 dark:text-gray-400">Fats</div>
              </div>
            </div>
            <div>
              <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">Ingredients</h3>
              {recipe.ingredients ? (
                <div className="text-gray-700 dark:text-gray-300 text-sm">
                  {recipe.ingredients.split(',').length > 1 ? (
                    <ul className="list-disc list-inside space-y-1">
                      {recipe.ingredients.split(',').map((ingredient, idx) => (
                        <li key={idx}>{ingredient.trim()}</li>
                      ))}
                    </ul>
                  ) : (
                    <p>{recipe.ingredients}</p>
                  )}
                </div>
              ) : (
                <p className="text-gray-500 dark:text-gray-400 text-sm italic">No ingredients listed</p>
              )}
            </div>
            <div>
              <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">Instructions</h3>
              {formattedInstructions.length > 0 ? (
                <ol className="text-gray-700 dark:text-gray-300 text-sm space-y-2">
                  {formattedInstructions.map((step, idx) => (
                    <li key={idx} className="flex gap-3">
                      <span className="font-semibold text-purple-600 dark:text-purple-400 min-w-[20px]">{idx + 1}.</span>
                      <span>{step}</span>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="text-gray-700 dark:text-gray-300 text-sm">{recipe.instructions}</p>
              )}
            </div>
            <div className="flex items-center justify-between pt-4 border-t border-gray-200 dark:border-gray-700">
              <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                <span>🕒 {recipe.ready_in_minutes} minutes</span>
                {recipe.diet_tags.map((tag, idx) => (
                  <span key={idx} className="px-2 py-1 bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-300 rounded-full text-xs">
                    {tag}
                  </span>
                ))}
              </div>
              {resolveRecipeUrl(recipe) && (
                <a
                  href={resolveRecipeUrl(recipe) as string}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-sm transition-colors no-underline"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                  View Original Recipe
                </a>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  };

  // Exercise Modal Component
  const ExerciseModal = ({ exercise, onClose }: { exercise: WorkoutOption; onClose: () => void }) => {
    const formattedInstructions = formatInstructions(exercise.instructions);
    
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
        <div className="bg-white dark:bg-gray-800 rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
          <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">{exercise.name}</h2>
            <button onClick={onClose} className="text-gray-500 hover:text-gray-700">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="p-6 space-y-4">
            <div className="grid grid-cols-3 gap-4 text-center">
              <div className="p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
                <div className="text-lg font-bold text-purple-600 dark:text-purple-400">4×10-12</div>
                <div className="text-xs text-gray-600 dark:text-gray-400">Sets × Reps</div>
              </div>
              <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                <div className={`text-lg font-bold ${getMETColor(exercise.estimated_met)}`}>{exercise.estimated_met}</div>
                <div className="text-xs text-gray-600 dark:text-gray-400">MET Value</div>
              </div>
              <div className="p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
                <div className="text-lg font-bold text-green-600 dark:text-green-400 capitalize">{exercise.equipment}</div>
                <div className="text-xs text-gray-600 dark:text-gray-400">Equipment</div>
              </div>
            </div>
            <div>
              <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">Target Muscle</h3>
              <span className="px-3 py-1 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded-full text-sm font-medium capitalize">
                {exercise.target_muscle}
              </span>
            </div>
            <div>
              <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">Instructions</h3>
              {formattedInstructions.length > 0 ? (
                <ol className="text-gray-700 dark:text-gray-300 text-sm space-y-2 leading-relaxed">
                  {formattedInstructions.map((step, idx) => (
                    <li key={idx} className="flex gap-3">
                      <span className="font-semibold text-purple-600 dark:text-purple-400 min-w-[20px]">{idx + 1}.</span>
                      <span>{step}</span>
                    </li>
                  ))}
                </ol>
              ) : (
                <div className="text-gray-700 dark:text-gray-300 text-sm leading-relaxed whitespace-pre-line">
                  {exercise.instructions}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  };

  // All Recommendations Modal Component
  const AllRecommendationsModal = ({ onClose }: { onClose: () => void }) => (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white dark:bg-gray-800 rounded-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">All AI Recommendations</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-700">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="p-6 space-y-6">
          {result?.plan.ai_recommendations.personalized_notes && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">Personalized Notes</h3>
              <div className="space-y-2">
                {result.plan.ai_recommendations.personalized_notes.map((note, idx) => (
                  <div key={idx} className="p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                    <p className="text-blue-700 dark:text-blue-400 text-sm">{note}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
          {result?.plan.ai_recommendations.nutrition_tips && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">Nutrition Tips</h3>
              <div className="space-y-2">
                {result.plan.ai_recommendations.nutrition_tips.map((tip, idx) => (
                  <div key={idx} className="p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
                    <p className="text-green-700 dark:text-green-400 text-sm">{tip}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
          {result?.plan.ai_recommendations.workout_tips && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">Workout Tips</h3>
              <div className="space-y-2">
                {result.plan.ai_recommendations.workout_tips.map((tip, idx) => (
                  <div key={idx} className="p-3 bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 rounded-lg">
                    <p className="text-purple-700 dark:text-purple-400 text-sm">{tip}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
          {result?.plan.ai_recommendations.safety_notes && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">Safety Notes</h3>
              <div className="space-y-2">
                {result.plan.ai_recommendations.safety_notes.map((note, idx) => (
                  <div key={idx} className="p-3 bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800 rounded-lg">
                    <p className="text-orange-700 dark:text-orange-400 text-sm">{note}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4">
        <div className="max-w-[1800px] mx-auto flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-purple-600 to-purple-700 rounded-xl flex items-center justify-center text-white font-bold text-lg">
            AH
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">AI Health Assistant</h1>
            <p className="text-sm text-gray-600 dark:text-gray-400">Your personalized fitness & nutrition coach</p>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <div className="max-w-[1800px] mx-auto p-6">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          
          {/* Main Content - 75% width (8/12 columns) */}
          <div className="lg:col-span-8 space-y-6">
            
            {/* Empty State */}
            {!result && !loading && (
              <div className="bg-white dark:bg-gray-800 rounded-xl shadow border border-gray-200 dark:border-gray-700 p-8 text-center">
                <div className="w-24 h-24 bg-gradient-to-br from-purple-100 to-purple-200 dark:from-purple-900/20 dark:to-purple-800/20 rounded-3xl flex items-center justify-center text-5xl mb-6 mx-auto">
                  💪
                </div>
                <h3 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-3">
                  Ready to Transform Your Fitness Journey?
                </h3>
                <p className="text-gray-500 dark:text-gray-400 text-lg mb-2">
                  Fill out your profile in the sidebar and generate your personalized plan
                </p>
                <p className="text-gray-400 dark:text-gray-600 text-sm">
                  AI-powered meal and workout recommendations await
                </p>
              </div>
            )}

            {/* Loading State - staged progress */}
            {loading && (
              <div className="bg-white dark:bg-gray-800 rounded-xl shadow border border-gray-200 dark:border-gray-700 p-8">
                <div className="flex flex-col items-center text-center mb-6">
                  <div className="relative w-16 h-16 mb-4">
                    <div className="absolute inset-0 rounded-full border-4 border-purple-100 dark:border-purple-900/30"></div>
                    <div className="absolute inset-0 rounded-full border-4 border-purple-600 border-t-transparent animate-spin"></div>
                    <div className="absolute inset-0 flex items-center justify-center text-purple-600 dark:text-purple-400 font-bold text-sm">
                      {Math.round(progress)}%
                    </div>
                  </div>
                  <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100">
                    Building your personalized plan
                  </h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                    This usually takes about a minute. Hang tight.
                  </p>
                </div>

                {/* Progress bar */}
                <div className="w-full h-3 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden mb-6">
                  <div
                    className="h-full bg-gradient-to-r from-purple-500 to-indigo-600 rounded-full transition-all duration-500 ease-out"
                    style={{ width: `${progress}%` }}
                  ></div>
                </div>

                {/* Stage checklist */}
                <ul className="space-y-3 max-w-md mx-auto">
                  {LOADING_STAGES.map((stage, i) => {
                    const done = i < stageIndex;
                    const active = i === stageIndex;
                    return (
                      <li key={i} className="flex items-center gap-3">
                        <span
                          className={`flex items-center justify-center w-6 h-6 rounded-full text-xs flex-shrink-0 transition-colors ${
                            done
                              ? "bg-green-500 text-white"
                              : active
                              ? "bg-purple-600 text-white"
                              : "bg-gray-200 dark:bg-gray-700 text-gray-400"
                          }`}
                        >
                          {done ? "✓" : active ? (
                            <span className="w-2 h-2 bg-white rounded-full animate-pulse"></span>
                          ) : (
                            i + 1
                          )}
                        </span>
                        <span
                          className={`text-sm transition-colors ${
                            active
                              ? "text-gray-900 dark:text-gray-100 font-medium"
                              : done
                              ? "text-gray-500 dark:text-gray-400 line-through"
                              : "text-gray-400 dark:text-gray-500"
                          }`}
                        >
                          {stage.label}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}

            {/* Results */}
            {result?.plan && (
              <div className="space-y-6">
                
                {/* 1. Profile & Goals - Two cards side-by-side */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Profile Card */}
                  <div className="bg-white dark:bg-gray-800 rounded-xl shadow border border-gray-200 dark:border-gray-700 p-5">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4 flex items-center gap-2">
                      ♙ Profile & Goals
                    </h3>
                    <div className="space-y-3 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="w-24 flex items-center gap-2 text-gray-600 dark:text-gray-400">⏱️ Age</span>
                        <span className="font-semibold text-gray-900 dark:text-gray-100">
                          {result.plan.user_profile_summary.age} years
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="w-24 flex items-center gap-2 text-gray-600 dark:text-gray-400">⚥ Sex</span>
                        <span className="font-semibold text-gray-900 dark:text-gray-100">
                          {result.plan.user_profile_summary.sex}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="w-24 flex items-center gap-2 text-gray-600 dark:text-gray-400">⚖️ Weight</span>
                        <span className="font-semibold text-gray-900 dark:text-gray-100">
                          {result.plan.user_profile_summary.weight_kg} kg
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="w-24 flex items-center gap-2 text-gray-600 dark:text-gray-400">↕️ Height</span>
                        <span className="font-semibold text-gray-900 dark:text-gray-100">
                          {result.plan.user_profile_summary.height_cm} cm
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="w-24 flex items-center gap-2 text-gray-600 dark:text-gray-400">◎ BMI</span>
                        <span className="font-semibold text-gray-900 dark:text-gray-100">
                          {result.plan.user_profile_summary.bmi.toFixed(1)} 
                          <span className={`ml-1 ${getBMICategory(result.plan.user_profile_summary.bmi).color}`}>
                            {getBMICategory(result.plan.user_profile_summary.bmi).category}
                          </span>
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="w-24 flex items-center gap-2 text-gray-600 dark:text-gray-400">♟️ Activity</span>
                        <span className="font-semibold text-gray-900 dark:text-gray-100 capitalize">
                          {result.plan.user_profile_summary.activity_level.replace('_', ' ')}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Goals Card */}
                  <div className="bg-white dark:bg-gray-800 rounded-xl shadow border border-gray-200 dark:border-gray-700 p-5">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4 flex items-center gap-2">
                      ◎ Goals
                    </h3>
                    <div className="mb-4 p-3 bg-gray-50 dark:bg-gray-900/50 rounded-lg border-l-4 border-purple-500">
                      <p className="text-sm text-gray-700 dark:text-gray-300 italic">
                        "{coachQuery}"
                      </p>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <span className="px-3 py-1 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded-full text-xs font-medium text-center">
                        ♬ {result.plan.plan_summary.goal_detected || "Personalized Goal"}
                      </span>
                      <span className="px-3 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-full text-xs font-medium text-center">
                        〽️ {result.plan.plan_summary.focus}
                      </span>
                      <span className="px-3 py-1 bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 rounded-full text-xs font-medium text-center">
                        ▣ {result.plan.plan_summary.difficulty_level}
                      </span>
                      <span className="px-3 py-1 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 rounded-full text-xs font-medium text-center">
                        ♟️ {result.plan.plan_summary.training_frequency_per_week || result.plan.intent?.training_frequency_per_week || "—"} day(s)/week
                      </span>
                    </div>
                  </div>
                </div>
                {/* 2. Plan Summary & Nutrition - Two cards side-by-side */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Plan Summary Card */}
                  <div className="bg-white dark:bg-gray-800 rounded-xl shadow border border-gray-200 dark:border-gray-700 p-5">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4 flex items-center gap-2">
                      ▣ Plan Summary
                    </h3>
                    <div className="space-y-3 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-2 text-gray-600 dark:text-gray-400">⚕️ Plan Type</span>
                        <span className="font-semibold text-gray-900 dark:text-gray-100 text-right">{result.plan.plan_summary.title}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-2 text-gray-600 dark:text-gray-400">♨️ Daily Calories</span>
                        <span className="font-semibold text-gray-900 dark:text-gray-100">
                          {Math.round(result.plan.nutrition_summary.avg_daily_calories)} kcal
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-2 text-gray-600 dark:text-gray-400">♜ Protein Target</span>
                        <span className="font-semibold text-gray-900 dark:text-gray-100">
                          {Math.round(result.plan.nutrition_summary.avg_daily_protein_g)} g/day
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-2 text-gray-600 dark:text-gray-400">⏱️ Duration</span>
                        <span className="font-semibold text-gray-900 dark:text-gray-100">
                          {result.plan.weekly_calendar.length} {result.plan.weekly_calendar.length === 1 ? "Day" : "Days"}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-2 text-gray-600 dark:text-gray-400">◎ Plan Level</span>
                        <span className="px-3 py-1 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded-full text-xs font-medium">
                          {result.plan.plan_summary.difficulty_level}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Nutrition Summary Card */}
                  <div className="bg-white dark:bg-gray-800 rounded-xl shadow border border-gray-200 dark:border-gray-700 p-5">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
                      Nutrition Summary - <span className="text-purple-600 dark:text-purple-400">{getDayName()}</span>
                    </h3>
                    <div className="flex items-center gap-8">
                      <div className="flex-shrink-0">
                        <DonutChart 
                          calories={result.plan.weekly_calendar[selectedDay]?.daily_totals.calories || result.plan.nutrition_summary.avg_daily_calories}
                          protein={result.plan.weekly_calendar[selectedDay]?.daily_totals.protein_g || result.plan.nutrition_summary.avg_daily_protein_g}
                          carbs={result.plan.weekly_calendar[selectedDay]?.daily_totals.carbs_g || result.plan.nutrition_summary.avg_daily_carbs_g}
                          fats={result.plan.weekly_calendar[selectedDay]?.daily_totals.fats_g || result.plan.nutrition_summary.avg_daily_fats_g}
                        />
                      </div>
                      <div className="text-sm space-y-3 flex-1 ml-4">
                        <div className="flex items-center gap-3">
                          <div className="w-3 h-3 bg-purple-500 rounded-full flex-shrink-0"></div>
                          <span className="text-gray-700 dark:text-gray-300 font-medium">
                            Protein: {Math.round(result.plan.weekly_calendar[selectedDay]?.daily_totals.protein_g || result.plan.nutrition_summary.avg_daily_protein_g)}g
                          </span>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="w-3 h-3 bg-blue-500 rounded-full flex-shrink-0"></div>
                          <span className="text-gray-700 dark:text-gray-300 font-medium">
                            Carbs: {Math.round(result.plan.weekly_calendar[selectedDay]?.daily_totals.carbs_g || result.plan.nutrition_summary.avg_daily_carbs_g)}g
                          </span>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="w-3 h-3 bg-orange-500 rounded-full flex-shrink-0"></div>
                          <span className="text-gray-700 dark:text-gray-300 font-medium">
                            Fat: {Math.round(result.plan.weekly_calendar[selectedDay]?.daily_totals.fats_g || result.plan.nutrition_summary.avg_daily_fats_g)}g
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* 3. Weekly Plan */}
                <div className="bg-white dark:bg-gray-800 rounded-xl shadow border border-gray-200 dark:border-gray-700 overflow-hidden">
                  <div className="bg-gradient-to-r from-purple-600 to-indigo-600 px-6 py-4">
                    <h2 className="text-xl font-semibold text-white flex items-center gap-2">
                      ▦ Your Plan {result.plan.weekly_calendar.length > 1 ? `(${result.plan.weekly_calendar.length} Days)` : "(1 Day)"}
                    </h2>
                  </div>
                  <div className="p-6">
                    <div className="flex flex-wrap gap-3">
                      {result.plan.weekly_calendar.map((day, idx) => (
                        <button
                          key={idx}
                          onClick={() => setSelectedDay(idx)}
                          className={`flex-1 min-w-[90px] p-4 rounded-xl border transition-all text-center ${
                            selectedDay === idx
                              ? 'bg-purple-600 text-white border-purple-600 shadow-lg scale-105'
                              : 'bg-gray-50 dark:bg-gray-900/50 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800'
                          }`}
                        >
                          <div className="font-semibold text-sm">{day.day.slice(0, 3)}</div>
                          <div className="text-xs mt-1 opacity-80">{day.is_rest_day ? "Rest" : day.workout.focus}</div>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* 4. Selected Day Display */}
                {result.plan.weekly_calendar[selectedDay] && (
                  <>
                    {/* 5. Daily Meals (dynamic meal types + multi-recipe support) */}
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                      {result.plan.weekly_calendar[selectedDay].meals.map((meal, mealIdx) => {
                        const mt = meal.meal_type.toLowerCase();
                        const icon = mt.includes("breakfast")
                          ? "☀️"
                          : mt.includes("lunch")
                          ? "🍽️"
                          : mt.includes("dinner")
                          ? "🌙"
                          : "🍪";
                        const items = resolveMealRecipes(meal, getCatalog(result.plan));
                        const mealCals = items.reduce((s, it) => s + scaled(it.recipe.base_calories, it.multiplier), 0);
                        const mealProtein = items.reduce((s, it) => s + scaled(it.recipe.base_protein_g, it.multiplier), 0);

                        return (
                          <div key={mealIdx} className="bg-white dark:bg-gray-800 rounded-xl shadow border border-gray-200 dark:border-gray-700 p-4">
                            <div className="border-b border-gray-200 dark:border-gray-700 pb-2 mb-3 flex items-center justify-between">
                              <h4 className="font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                                {icon} {meal.meal_type}
                              </h4>
                              {items.length > 0 && (
                                <span className="text-xs text-gray-500 dark:text-gray-400">
                                  🔥 {mealCals} kcal · 💪 {mealProtein}g
                                </span>
                              )}
                            </div>
                            {items.length > 0 ? (
                              <div className="space-y-3">
                                {items.map(({ recipe, multiplier }, i) => (
                                  <div key={i} className="rounded-lg border border-gray-100 dark:border-gray-700 p-3">
                                    <div className="flex items-start justify-between gap-2">
                                      <h5 className="font-bold text-gray-900 dark:text-gray-100 text-sm">
                                        {recipe.recipe_name}
                                      </h5>
                                      {multiplier !== 1.0 && (
                                        <span className="text-xs px-2 py-0.5 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded-full whitespace-nowrap">
                                          ×{multiplier}
                                        </span>
                                      )}
                                    </div>
                                    <div className="text-xs text-gray-600 dark:text-gray-400 mt-1 mb-2">
                                      🔥 {scaled(recipe.base_calories, multiplier)} kcal · 💪 {scaled(recipe.base_protein_g, multiplier)}g protein
                                    </div>
                                    <button
                                      onClick={() => setShowRecipeModal(recipe)}
                                      className="w-full bg-purple-600 hover:bg-purple-700 text-white text-xs py-2 px-3 rounded-lg transition-colors"
                                    >
                                      View Full Recipe →
                                    </button>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <div className="text-gray-500 dark:text-gray-400 text-sm italic text-center py-4">
                                No items planned
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                    {/* 6. Workout Table */}
                    <div className="bg-white dark:bg-gray-800 rounded-xl shadow border border-gray-200 dark:border-gray-700 overflow-hidden">
                      <div className="bg-gradient-to-r from-purple-600 to-indigo-600 px-6 py-4">
                        <h2 className="text-xl font-semibold text-white flex items-center gap-2">
                          ♬ {result.plan.weekly_calendar[selectedDay].is_rest_day ? "Rest & Recovery" : `Workout – ${result.plan.weekly_calendar[selectedDay].workout.focus}`}
                        </h2>
                        <p className="text-purple-100 text-sm">
                          {result.plan.weekly_calendar[selectedDay].is_rest_day
                            ? "Active recovery day"
                            : `Total Exercises: ${result.plan.weekly_calendar[selectedDay].workout.exercise_indices.length} · ${result.plan.weekly_calendar[selectedDay].workout.duration_min} min`}
                        </p>
                      </div>
                      {result.plan.weekly_calendar[selectedDay].is_rest_day ||
                      result.plan.weekly_calendar[selectedDay].workout.exercise_indices.length === 0 ? (
                        <div className="p-6 text-center text-gray-600 dark:text-gray-400">
                          🧘 Rest / active recovery day. Light walking, stretching, or mobility work is recommended.
                          {!!result.plan.weekly_calendar[selectedDay].workout.cardio_min && (
                            <div className="mt-3 inline-flex items-center gap-2 px-4 py-2 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 rounded-lg text-sm">
                              🏃 {result.plan.weekly_calendar[selectedDay].workout.cardio_note || `${result.plan.weekly_calendar[selectedDay].workout.cardio_min} min light cardio`}
                            </div>
                          )}
                        </div>
                      ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full">
                          <thead>
                            <tr className="border-b border-gray-200 dark:border-gray-700">
                              <th className="text-left p-4 text-sm font-medium text-gray-700 dark:text-gray-300">#</th>
                              <th className="text-left p-4 text-sm font-medium text-gray-700 dark:text-gray-300">Exercise</th>
                              <th className="text-left p-4 text-sm font-medium text-gray-700 dark:text-gray-300">Target</th>
                              <th className="text-left p-4 text-sm font-medium text-gray-700 dark:text-gray-300">Sets × Reps</th>
                              <th className="text-left p-4 text-sm font-medium text-gray-700 dark:text-gray-300">Rest</th>
                              <th className="text-left p-4 text-sm font-medium text-gray-700 dark:text-gray-300">MET</th>
                              <th className="text-left p-4 text-sm font-medium text-gray-700 dark:text-gray-300">Equipment</th>
                              <th className="text-left p-4 text-sm font-medium text-gray-700 dark:text-gray-300">Instructions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {result.plan.weekly_calendar[selectedDay].workout.exercise_indices.map((exIdx, i) => {
                              const exercise = result.plan.workout_options[exIdx];
                              return exercise ? (
                                <tr key={i} className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800/50">
                                  <td className="p-4 text-purple-600 dark:text-purple-400 font-bold">{i + 1}</td>
                                  <td className="p-4 font-bold text-gray-900 dark:text-gray-100">{exercise.name}</td>
                                  <td className="p-4 text-gray-700 dark:text-gray-300 capitalize">{exercise.target_muscle}</td>
                                  <td className="p-4 text-gray-700 dark:text-gray-300">4 × 10–12</td>
                                  <td className="p-4 text-gray-700 dark:text-gray-300">60–90s</td>
                                  <td className={`p-4 font-medium ${getMETColor(exercise.estimated_met)}`}>{exercise.estimated_met.toFixed(1)}</td>
                                  <td className="p-4 text-gray-700 dark:text-gray-300 capitalize">{exercise.equipment}</td>
                                  <td className="p-4">
                                    <button 
                                      onClick={() => setShowExerciseModal(exercise)}
                                      className="text-purple-600 dark:text-purple-400 hover:underline text-sm"
                                    >
                                      View Full Instructions →
                                    </button>
                                  </td>
                                </tr>
                              ) : null;
                            })}
                          </tbody>
                        </table>
                        {!!result.plan.weekly_calendar[selectedDay].workout.cardio_min && (
                          <div className="m-4 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg flex items-start gap-3">
                            <span className="text-xl">🏃</span>
                            <div>
                              <div className="font-semibold text-blue-800 dark:text-blue-300 text-sm">
                                Cardio Finisher · {result.plan.weekly_calendar[selectedDay].workout.cardio_min} min
                              </div>
                              <p className="text-blue-700 dark:text-blue-400 text-sm">
                                {result.plan.weekly_calendar[selectedDay].workout.cardio_note}
                              </p>
                            </div>
                          </div>
                        )}
                      </div>
                      )}
                    </div>
                  </>
                )}

              </div>
            )}

          </div>

          {/* Sidebar - 25% width (4/12 columns) */}
          <aside className="lg:col-span-4 space-y-6 lg:sticky lg:top-6 lg:h-fit">
            
            {/* Ask AI Coach Form */}
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow border border-gray-200 dark:border-gray-700 p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-8 h-8 bg-gradient-to-br from-purple-500 to-indigo-600 rounded-lg flex items-center justify-center text-white text-lg">
                  🌐
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">AI Fitness Planner</h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Generate personalized fitness and nutrition plans based on your goals, preferences, and lifestyle.</p>
                </div>
              </div>

              <div className="mb-4">
                <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Your Profile (used to personalize your plan)</h4>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">⚕️ Age</label>
                    <input 
                      type="number" 
                      name="age" 
                      min={13}
                      max={100}
                      value={formData.age} 
                      onChange={handleChange}
                      className={`w-full rounded-lg border px-3 py-2 text-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 transition-all bg-white dark:bg-gray-900 ${fieldErrors.age ? "border-red-400 dark:border-red-500" : "border-gray-300 dark:border-gray-600"}`}
                      required 
                    />
                    {fieldErrors.age && <p className="text-xs text-red-600 dark:text-red-400 mt-1">{fieldErrors.age}</p>}
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">〽️ Sex</label>
                    <select 
                      name="sex" 
                      value={formData.sex} 
                      onChange={handleChange}
                      className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 transition-all"
                    >
                      <option value="Male">Male</option>
                      <option value="Female">Female</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">▣ Weight (kg)</label>
                    <input 
                      type="number" 
                      name="weight_kg" 
                      min={25}
                      max={400}
                      step="0.1"
                      value={formData.weight_kg} 
                      onChange={handleChange}
                      className={`w-full rounded-lg border px-3 py-2 text-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 transition-all bg-white dark:bg-gray-900 ${fieldErrors.weight_kg ? "border-red-400 dark:border-red-500" : "border-gray-300 dark:border-gray-600"}`}
                      required 
                    />
                    {fieldErrors.weight_kg && <p className="text-xs text-red-600 dark:text-red-400 mt-1">{fieldErrors.weight_kg}</p>}
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">↕️ Height (cm)</label>
                    <input 
                      type="number" 
                      name="height_cm" 
                      min={90}
                      max={250}
                      value={formData.height_cm} 
                      onChange={handleChange}
                      placeholder="e.g. 180"
                      className={`w-full rounded-lg border px-3 py-2 text-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 transition-all bg-white dark:bg-gray-900 ${fieldErrors.height_cm ? "border-red-400 dark:border-red-500" : "border-gray-300 dark:border-gray-600"}`}
                      required 
                    />
                    {fieldErrors.height_cm && <p className="text-xs text-red-600 dark:text-red-400 mt-1">{fieldErrors.height_cm}</p>}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">♨️ Activity Level</label>
                  <select 
                    name="activity_level" 
                    value={formData.activity_level} 
                    onChange={handleChange}
                    className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 transition-all"
                  >
                    {ACTIVITY_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                  <p className="mt-2 text-xs text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-900/50 border border-gray-200 dark:border-gray-700 rounded-lg p-2">
                    {ACTIVITY_OPTIONS.find((o) => o.value === formData.activity_level)?.benchmark}
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    What do you want to achieve?
                  </label>
                  <textarea 
                    name="coachQuery" 
                    value={coachQuery} 
                    onChange={(e) => { setCoachQuery(e.target.value); setFieldErrors((p) => ({ ...p, query: "" })); }} 
                    rows={4}
                    placeholder="e.g., I want to build muscle and lose fat with high-protein meals..."
                    className={`w-full rounded-lg border px-3 py-2 text-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 transition-all resize-none bg-white dark:bg-gray-900 ${fieldErrors.query ? "border-red-400 dark:border-red-500" : "border-gray-300 dark:border-gray-600"}`}
                    required 
                  />
                  {fieldErrors.query && <p className="text-xs text-red-600 dark:text-red-400 mt-1">{fieldErrors.query}</p>}
                  
                  {/* Guidance Section */}
                  <div className="mt-3 bg-gray-50 dark:bg-gray-900/50 rounded-lg p-3 border border-gray-200 dark:border-gray-700">
                    <h4 className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">Example Goals:</h4>
                    <ul className="text-xs text-gray-600 dark:text-gray-400 space-y-1 mb-2">
                      <li>• "I want to lose fat while maintaining muscle and I prefer quick high-protein meals."</li>
                      <li>• "I want a leg hypertrophy routine with a high-protein diet and 4 workout days per week."</li>
                      <li>• "I need a gluten-free meal plan and beginner-friendly workouts."</li>
                      <li>• "I want to improve endurance for hiking and I prefer affordable meals."</li>
                    </ul>
                    <p className="text-xs text-gray-600 dark:text-gray-400 font-medium mb-1">Include details about:</p>
                    <div className="grid grid-cols-2 gap-x-3 text-xs text-gray-500 dark:text-gray-500">
                      <div>
                        <p>• Fitness goals</p>
                        <p>• Dietary preferences</p>
                        <p>• Allergies or restrictions</p>
                        <p>• Available equipment</p>
                      </div>
                      <div>
                        <p>• Workout preferences</p>
                        <p>• Lifestyle details</p>
                        <p>• Desired outcomes</p>
                        <p>• Time constraints</p>
                      </div>
                    </div>
                  </div>
                </div>

                <button 
                  type="submit" 
                  disabled={loading}
                  className="w-full bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white font-semibold py-3 px-6 rounded-lg shadow-md hover:shadow-lg transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? (
                    <span className="flex items-center justify-center gap-2">
                      <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Generating...
                    </span>
                  ) : (
                    <span className="flex items-center justify-center gap-2">
                      ✧ Generate My Plan
                    </span>
                  )}
                </button>
              </form>
              
              {error && (
                <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                  <p className="text-red-700 dark:text-red-400 text-sm flex items-center gap-2">
                    <span>⚠️</span>
                    {error}
                  </p>
                </div>
              )}
            </div>

            {/* AI Coach Tips */}
            {result?.plan && (
              <div className="bg-white dark:bg-gray-800 rounded-xl shadow border border-gray-200 dark:border-gray-700 p-6">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4 flex items-center gap-2">
                  ✦ AI Coach Tips
                </h3>
                <div className="p-4 bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20 border border-purple-200 dark:border-purple-800 rounded-lg">
                  <div className="flex items-start gap-3">
                    <span className="text-lg">💡</span>
                    <div>
                      <h4 className="font-semibold text-purple-800 dark:text-purple-300 text-sm mb-1">Main Recommendation</h4>
                      <p className="text-purple-700 dark:text-purple-400 text-sm">
                        {result.plan.ai_recommendations.main_tip}
                      </p>
                    </div>
                  </div>
                </div>
                
                <button 
                  onClick={() => setShowAllRecommendations(true)}
                  className="w-full mt-4 text-purple-600 dark:text-purple-400 hover:text-purple-800 dark:hover:text-purple-200 text-sm font-medium text-center py-2 border border-purple-200 dark:border-purple-700 rounded-lg hover:bg-purple-50 dark:hover:bg-purple-900/20 transition-colors"
                >
                  View All Recommendations →
                </button>
              </div>
            )}
            
            {/* Export Plan */}
            {result?.plan && (
              <div className="bg-white dark:bg-gray-800 rounded-xl shadow border border-gray-200 dark:border-gray-700 p-6">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2 flex items-center gap-2">
                  ⇩ Export Plan
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                  Export your full plan as a PDF (profile, summary & one page per day)
                </p>
                <button
                  onClick={handleExportPDF}
                  disabled={exporting}
                  className="w-full bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-3 px-4 rounded-lg transition-colors flex items-center justify-center gap-2"
                >
                  {exporting ? "Generating PDF…" : "⇩ Export Plan (PDF)"}
                </button>
              </div>
            )}

          </aside>

        </div>
      </div>

      {/* Modals */}
      {showRecipeModal && <RecipeModal recipe={showRecipeModal} onClose={() => setShowRecipeModal(null)} />}
      {showExerciseModal && <ExerciseModal exercise={showExerciseModal} onClose={() => setShowExerciseModal(null)} />}
      {showAllRecommendations && <AllRecommendationsModal onClose={() => setShowAllRecommendations(false)} />}
    </div>
  );
}