# guides/indoor_plant_guides.py
# Full indoor plant care guide (matches your 47 labels)
INDOOR_PLANT_GUIDE = {
    "African Violet (Saintpaulia ionantha)": {
        "category": "Flowering",
        "difficulty": "Medium",
        "light": "Bright indirect light",
        "watering": {
            "frequency": "When top 1–2 cm soil is dry (usually 5–7 days)",
            "method": "Bottom-water preferred; avoid wetting leaves",
            "notes": "Use room-temperature water"
        },
        "temperature": "18–24°C",
        "humidity": "High (50–70%)",
        "soil": "African violet potting mix (light, airy, well-draining)",
        "fertilizer": "Balanced fertilizer at half strength every 2 weeks in active growth",
        "common_problems": [
            "Leaf spots (water on leaves / cold water)",
            "Crown rot (overwatering)",
            "No blooms (low light / low feeding)"
        ],
        "pests": ["Mealybugs", "Aphids", "Thrips"],
        "pet_safety": "Safe",
        "care_tips": ["Keep warm", "Rotate pot weekly", "Remove faded flowers"]
    },

    "Aloe Vera": {
        "category": "Succulent",
        "difficulty": "Easy",
        "light": "Bright light; tolerates some direct sun",
        "watering": {
            "frequency": "Every 2–3 weeks (less in winter)",
            "method": "Soak and dry; let soil dry fully",
            "notes": "Overwatering is the #1 killer"
        },
        "temperature": "18–30°C",
        "humidity": "Low",
        "soil": "Cactus/succulent mix + perlite",
        "fertilizer": "Cactus fertilizer monthly (spring–summer)",
        "common_problems": ["Root rot", "Soft leaves (too much water)", "Stretching (low light)"],
        "pests": ["Mealybugs", "Scale"],
        "pet_safety": "Toxic",
        "care_tips": ["Use pot with drainage", "Avoid misting"]
    },

    "Anthurium (Anthurium andraeanum)": {
        "category": "Flowering",
        "difficulty": "Medium",
        "light": "Bright indirect light",
        "watering": {
            "frequency": "Weekly (when top 2–3 cm soil is dry)",
            "method": "Water thoroughly; don’t leave standing water",
            "notes": "Prefers evenly moist soil"
        },
        "temperature": "20–28°C",
        "humidity": "High",
        "soil": "Chunky airy mix (orchid bark + peat/coco + perlite)",
        "fertilizer": "Balanced fertilizer monthly",
        "common_problems": ["Brown leaf edges (dry air)", "Yellow leaves (overwatering)"],
        "pests": ["Spider mites", "Mealybugs"],
        "pet_safety": "Toxic",
        "care_tips": ["Mist or use humidifier", "Bright indirect = more flowers"]
    },

    "Areca Palm (Dypsis lutescens)": {
        "category": "Palm",
        "difficulty": "Easy",
        "light": "Bright indirect; avoid harsh direct sun",
        "watering": {
            "frequency": "1–2 times/week depending on heat",
            "method": "Keep slightly moist; don’t let it dry fully",
            "notes": "Sensitive to fluoride/chlorine"
        },
        "temperature": "18–26°C",
        "humidity": "Medium to high",
        "soil": "Well-draining palm mix",
        "fertilizer": "Palm fertilizer monthly (spring–summer)",
        "common_problems": ["Brown tips (dry air / water quality)", "Yellowing (low nutrients)"],
        "pests": ["Spider mites", "Scale"],
        "pet_safety": "Safe",
        "care_tips": ["Wipe leaves", "Increase humidity"]
    },

    "Asparagus Fern (Asparagus setaceus)": {
        "category": "Fern-like",
        "difficulty": "Medium",
        "light": "Bright indirect to partial shade",
        "watering": {
            "frequency": "Keep soil lightly moist",
            "method": "Water when surface begins to dry",
            "notes": "Hates drying out"
        },
        "temperature": "18–24°C",
        "humidity": "High",
        "soil": "Rich well-draining potting soil",
        "fertilizer": "Monthly during growth",
        "common_problems": ["Leaf drop (dry air/dry soil)", "Yellowing (too much sun)"],
        "pests": ["Aphids", "Spider mites"],
        "pet_safety": "Toxic",
        "care_tips": ["Mist frequently", "Avoid heat vents"]
    },

    "Begonia (Begonia spp.)": {
        "category": "Foliage/Flowering",
        "difficulty": "Medium",
        "light": "Bright indirect",
        "watering": {
            "frequency": "When top soil dries",
            "method": "Water at soil level; avoid wet leaves",
            "notes": "Overwatering causes rot"
        },
        "temperature": "18–24°C",
        "humidity": "High (but good airflow)",
        "soil": "Light well-draining mix",
        "fertilizer": "Every 2 weeks in growth",
        "common_problems": ["Powdery mildew", "Stem rot", "Leaf drop (cold)"],
        "pests": ["Mealybugs", "Thrips"],
        "pet_safety": "Toxic",
        "care_tips": ["Provide airflow", "Avoid direct sun"]
    },

    "Bird of Paradise (Strelitzia reginae)": {
        "category": "Tropical",
        "difficulty": "Medium",
        "light": "Very bright light; some direct sun helps",
        "watering": {
            "frequency": "Weekly (let top 3–5 cm dry)",
            "method": "Deep watering, then drain",
            "notes": "Less water in winter"
        },
        "temperature": "18–30°C",
        "humidity": "Medium",
        "soil": "Rich well-draining soil",
        "fertilizer": "Monthly spring–summer",
        "common_problems": ["Splitting leaves (normal)", "No flowers (not enough light)"],
        "pests": ["Spider mites", "Scale"],
        "pet_safety": "Toxic",
        "care_tips": ["Needs space", "Rotate for even growth"]
    },

    "Birds Nest Fern (Asplenium nidus)": {
        "category": "Fern",
        "difficulty": "Medium",
        "light": "Low to medium indirect light",
        "watering": {
            "frequency": "Keep soil slightly moist",
            "method": "Water around edge; avoid watering the center crown",
            "notes": "Soft water preferred"
        },
        "temperature": "18–26°C",
        "humidity": "High",
        "soil": "Peat-based airy mix",
        "fertilizer": "Monthly at half strength",
        "common_problems": ["Crispy edges (dry air)", "Yellow fronds (overwatering)"],
        "pests": ["Scale", "Mealybugs"],
        "pet_safety": "Safe",
        "care_tips": ["Use humidifier", "Avoid cold drafts"]
    },

    "Boston Fern (Nephrolepis exaltata)": {
        "category": "Fern",
        "difficulty": "Medium",
        "light": "Bright indirect light",
        "watering": {
            "frequency": "Keep consistently moist",
            "method": "Water when surface dries slightly",
            "notes": "Don’t let dry out"
        },
        "temperature": "16–24°C",
        "humidity": "High",
        "soil": "Loamy rich soil",
        "fertilizer": "Monthly",
        "common_problems": ["Leaf drop (dry air)", "Brown tips (low humidity)"],
        "pests": ["Spider mites"],
        "pet_safety": "Safe",
        "care_tips": ["Mist often", "Hanging basket works well"]
    },

    "Calathea": {
        "category": "Foliage",
        "difficulty": "Hard",
        "light": "Low to medium indirect light",
        "watering": {
            "frequency": "Keep evenly moist (not soggy)",
            "method": "Use filtered/low-mineral water",
            "notes": "Very sensitive to tap water"
        },
        "temperature": "18–26°C",
        "humidity": "High (60%+)",
        "soil": "Well-draining peat-based mix",
        "fertilizer": "Monthly (spring–summer)",
        "common_problems": ["Curling leaves (dry air)", "Brown edges (minerals/low humidity)"],
        "pests": ["Spider mites"],
        "pet_safety": "Safe",
        "care_tips": ["Humidifier is best", "Keep away from AC"]
    },

    "Cast Iron Plant (Aspidistra elatior)": {
        "category": "Low light",
        "difficulty": "Very Easy",
        "light": "Low to medium light",
        "watering": {
            "frequency": "Every 2–3 weeks",
            "method": "Let soil dry partly between waterings",
            "notes": "Tolerates neglect"
        },
        "temperature": "10–24°C",
        "humidity": "Low to medium",
        "soil": "Well-draining potting soil",
        "fertilizer": "Every 2 months",
        "common_problems": ["Yellow leaves (overwatering)"],
        "pests": ["Scale"],
        "pet_safety": "Safe",
        "care_tips": ["Perfect for dim rooms"]
    },

    "Chinese Money Plant (Pilea peperomioides)": {
        "category": "Foliage",
        "difficulty": "Easy",
        "light": "Bright indirect",
        "watering": {
            "frequency": "Weekly",
            "method": "Water when top 2 cm is dry",
            "notes": "Don’t keep soggy"
        },
        "temperature": "18–24°C",
        "humidity": "Medium",
        "soil": "Well-draining soil + perlite",
        "fertilizer": "Monthly",
        "common_problems": ["Leggy growth (low light)", "Droop (dry soil)"],
        "pests": ["Mealybugs"],
        "pet_safety": "Safe",
        "care_tips": ["Rotate often", "Easy to propagate via pups"]
    },

    "Chinese evergreen (Aglaonema)": {
        "category": "Low light",
        "difficulty": "Easy",
        "light": "Low to medium indirect",
        "watering": {
            "frequency": "Every 1–2 weeks",
            "method": "Water when top soil dries",
            "notes": "More light = more water"
        },
        "temperature": "18–26°C",
        "humidity": "Medium",
        "soil": "Well-draining potting soil",
        "fertilizer": "Monthly",
        "common_problems": ["Yellow leaves (overwatering)", "Brown tips (dry air)"],
        "pests": ["Spider mites"],
        "pet_safety": "Toxic",
        "care_tips": ["Great indoor plant", "Avoid cold drafts"]
    },

    "Christmas Cactus (Schlumbergera bridgesii)": {
        "category": "Cactus (tropical)",
        "difficulty": "Medium",
        "light": "Bright indirect",
        "watering": {
            "frequency": "Weekly during growth; less in winter",
            "method": "Keep slightly moist; don’t fully dry like desert cactus",
            "notes": "Too dry causes bud drop"
        },
        "temperature": "16–24°C",
        "humidity": "Medium",
        "soil": "Well-draining cactus mix + peat",
        "fertilizer": "Monthly spring–summer",
        "common_problems": ["Bud drop (stress)", "Soft stems (overwatering)"],
        "pests": ["Mealybugs"],
        "pet_safety": "Safe",
        "care_tips": ["Cool nights + short days help blooming"]
    },

    "Chrysanthemum": {
        "category": "Flowering",
        "difficulty": "Medium",
        "light": "Bright light; some direct sun",
        "watering": {
            "frequency": "Regular; keep evenly moist",
            "method": "Water at soil level",
            "notes": "Don’t let it wilt repeatedly"
        },
        "temperature": "15–21°C",
        "humidity": "Medium",
        "soil": "Rich well-draining soil",
        "fertilizer": "Every 2 weeks during flowering",
        "common_problems": ["Powdery mildew", "Bud drop (heat)"],
        "pests": ["Aphids", "Thrips"],
        "pet_safety": "Toxic",
        "care_tips": ["Pinch for bushiness", "Cooler temps prolong blooms"]
    },

    "Ctenanthe": {
        "category": "Prayer plant family",
        "difficulty": "Hard",
        "light": "Medium indirect",
        "watering": {
            "frequency": "Keep moist (not soggy)",
            "method": "Use filtered water",
            "notes": "Dislikes drying out"
        },
        "temperature": "18–26°C",
        "humidity": "High",
        "soil": "Peat-based airy mix",
        "fertilizer": "Monthly (spring–summer)",
        "common_problems": ["Brown edges (low humidity)", "Curling leaves (dry)"],
        "pests": ["Spider mites"],
        "pet_safety": "Safe",
        "care_tips": ["High humidity required"]
    },

    "Daffodils (Narcissus spp.)": {
        "category": "Bulb flowering",
        "difficulty": "Easy",
        "light": "Bright light",
        "watering": {
            "frequency": "Keep lightly moist during growth",
            "method": "Water when soil begins to dry",
            "notes": "After bloom, reduce watering"
        },
        "temperature": "10–18°C",
        "humidity": "Low",
        "soil": "Well-draining bulb mix",
        "fertilizer": "Bulb fertilizer during growth",
        "common_problems": ["Flopping stems (low light/too warm)"],
        "pests": ["Aphids"],
        "pet_safety": "Toxic",
        "care_tips": ["Cool temps extend bloom", "Let leaves yellow naturally"]
    },

    "Dracaena": {
        "category": "Foliage",
        "difficulty": "Easy",
        "light": "Medium indirect (tolerates low light)",
        "watering": {
            "frequency": "Every 1–2 weeks",
            "method": "Water when top 3–5 cm is dry",
            "notes": "Sensitive to fluoride/chlorine"
        },
        "temperature": "18–27°C",
        "humidity": "Medium",
        "soil": "Well-draining potting soil",
        "fertilizer": "Monthly",
        "common_problems": ["Brown tips (water quality)", "Yellowing (overwatering)"],
        "pests": ["Spider mites", "Mealybugs"],
        "pet_safety": "Toxic",
        "care_tips": ["Use filtered water if possible"]
    },

    "Dumb Cane (Dieffenbachia spp.)": {
        "category": "Foliage",
        "difficulty": "Medium",
        "light": "Bright indirect",
        "watering": {
            "frequency": "Weekly",
            "method": "Keep lightly moist",
            "notes": "Avoid soggy soil"
        },
        "temperature": "18–27°C",
        "humidity": "Medium to high",
        "soil": "Well-draining rich soil",
        "fertilizer": "Monthly",
        "common_problems": ["Yellow leaves (overwatering)", "Leaf drop (cold)"],
        "pests": ["Mealybugs", "Spider mites"],
        "pet_safety": "Toxic (sap irritant)",
        "care_tips": ["Wear gloves when pruning"]
    },

    "Elephant Ear (Alocasia spp.)": {
        "category": "Tropical",
        "difficulty": "Hard",
        "light": "Bright indirect",
        "watering": {
            "frequency": "Keep evenly moist",
            "method": "Water when top soil begins to dry",
            "notes": "Dormant in winter → water less"
        },
        "temperature": "20–30°C",
        "humidity": "High",
        "soil": "Chunky airy mix",
        "fertilizer": "Every 2 weeks spring–summer",
        "common_problems": ["Drooping leaves (dry air)", "Yellowing (too wet)"],
        "pests": ["Spider mites", "Thrips"],
        "pet_safety": "Toxic",
        "care_tips": ["Humidity is key", "Avoid drafts"]
    },

    "English Ivy (Hedera helix)": {
        "category": "Trailing",
        "difficulty": "Medium",
        "light": "Bright indirect (some direct sun ok)",
        "watering": {
            "frequency": "Weekly",
            "method": "Keep soil slightly moist",
            "notes": "Prefers cooler rooms"
        },
        "temperature": "10–21°C",
        "humidity": "Medium",
        "soil": "Well-draining soil",
        "fertilizer": "Monthly",
        "common_problems": ["Spider mites in dry air", "Leaf drop (heat)"],
        "pests": ["Spider mites", "Aphids"],
        "pet_safety": "Toxic",
        "care_tips": ["Cool temperature improves growth"]
    },

    "Hyacinth (Hyacinthus orientalis)": {
        "category": "Bulb flowering",
        "difficulty": "Easy",
        "light": "Bright light",
        "watering": {
            "frequency": "Moderate during growth",
            "method": "Keep lightly moist",
            "notes": "Avoid waterlogging"
        },
        "temperature": "10–18°C",
        "humidity": "Low",
        "soil": "Well-draining bulb mix",
        "fertilizer": "Bulb fertilizer during growth",
        "common_problems": ["Flopping stems (too warm/low light)"],
        "pests": ["Aphids"],
        "pet_safety": "Toxic",
        "care_tips": ["Cool temperatures extend bloom"]
    },

    "Iron Cross begonia (Begonia masoniana)": {
        "category": "Foliage",
        "difficulty": "Medium",
        "light": "Bright indirect",
        "watering": {
            "frequency": "When top soil dries",
            "method": "Water carefully; avoid soggy soil",
            "notes": "High humidity with airflow"
        },
        "temperature": "18–24°C",
        "humidity": "High",
        "soil": "Well-draining",
        "fertilizer": "Biweekly in growth",
        "common_problems": ["Mildew", "Rot"],
        "pests": ["Mealybugs"],
        "pet_safety": "Toxic",
        "care_tips": ["Avoid wet leaves", "Provide airflow"]
    },

    "Jade plant (Crassula ovata)": {
        "category": "Succulent",
        "difficulty": "Easy",
        "light": "Bright light; some direct sun",
        "watering": {
            "frequency": "Every 2–3 weeks",
            "method": "Let soil dry fully",
            "notes": "Less water in winter"
        },
        "temperature": "18–26°C",
        "humidity": "Low",
        "soil": "Cactus mix",
        "fertilizer": "Monthly spring–summer",
        "common_problems": ["Leaf drop (overwatering)", "Stretching (low light)"],
        "pests": ["Mealybugs"],
        "pet_safety": "Toxic",
        "care_tips": ["Prune to shape", "Rotate for even growth"]
    },

    "Kalanchoe": {
        "category": "Flowering succulent",
        "difficulty": "Easy",
        "light": "Bright light; some direct sun",
        "watering": {
            "frequency": "Every 2 weeks",
            "method": "Let soil dry between waterings",
            "notes": "Overwatering causes rot"
        },
        "temperature": "18–26°C",
        "humidity": "Low to medium",
        "soil": "Cactus/succulent mix",
        "fertilizer": "Monthly in growth",
        "common_problems": ["No flowers (low light)", "Soft stems (overwatering)"],
        "pests": ["Aphids", "Mealybugs"],
        "pet_safety": "Toxic",
        "care_tips": ["Short days encourage blooms"]
    },

    "Lilium (Hemerocallis)": {
        "category": "Flowering (daylily)",
        "difficulty": "Medium",
        "light": "Bright light / sun",
        "watering": {
            "frequency": "Keep moderately moist",
            "method": "Water when top dries",
            "notes": "Avoid soggy soil"
        },
        "temperature": "15–25°C",
        "humidity": "Medium",
        "soil": "Rich, well-draining",
        "fertilizer": "Every 2 weeks during active growth",
        "common_problems": ["Bud drop (heat)", "Yellow leaves (overwatering)"],
        "pests": ["Aphids"],
        "pet_safety": "Toxic to cats (very dangerous)",
        "care_tips": ["Bright light for blooms"]
    },

    "Lily of the valley (Convallaria majalis)": {
        "category": "Flowering",
        "difficulty": "Medium",
        "light": "Bright indirect / partial shade",
        "watering": {
            "frequency": "Keep evenly moist",
            "method": "Water when surface dries slightly",
            "notes": "Prefers cool conditions"
        },
        "temperature": "10–20°C",
        "humidity": "Medium",
        "soil": "Rich, well-draining",
        "fertilizer": "Monthly in growth",
        "common_problems": ["Wilting (heat)", "Leaf yellowing (dry soil)"],
        "pests": ["Aphids"],
        "pet_safety": "Highly toxic",
        "care_tips": ["Cool temps help flowering"]
    },

    "Money Tree (Pachira aquatica)": {
        "category": "Tree foliage",
        "difficulty": "Easy",
        "light": "Bright indirect",
        "watering": {
            "frequency": "Every 1–2 weeks",
            "method": "Water when top 3–5 cm dries",
            "notes": "Overwatering causes trunk rot"
        },
        "temperature": "18–27°C",
        "humidity": "Medium",
        "soil": "Well-draining mix",
        "fertilizer": "Monthly",
        "common_problems": ["Yellow leaves (overwatering)", "Leaf drop (cold drafts)"],
        "pests": ["Scale", "Mealybugs"],
        "pet_safety": "Mildly toxic",
        "care_tips": ["Rotate for balanced growth"]
    },

    "Monstera Deliciosa (Monstera deliciosa)": {
        "category": "Tropical foliage",
        "difficulty": "Medium",
        "light": "Bright indirect",
        "watering": {
            "frequency": "Every 1–2 weeks",
            "method": "Water when top soil dries",
            "notes": "Increase humidity for best leaves"
        },
        "temperature": "20–30°C",
        "humidity": "Medium to high",
        "soil": "Chunky airy mix (bark + coco/peat + perlite)",
        "fertilizer": "Monthly spring–summer",
        "common_problems": ["No splits (low light)", "Yellow leaves (overwatering)"],
        "pests": ["Spider mites", "Thrips"],
        "pet_safety": "Toxic",
        "care_tips": ["Use moss pole", "Wipe leaves"]
    },

    "Orchid": {
        "category": "Flowering",
        "difficulty": "Medium",
        "light": "Bright indirect",
        "watering": {
            "frequency": "Every 7–10 days",
            "method": "Soak roots then drain fully",
            "notes": "Never leave roots in water"
        },
        "temperature": "18–28°C",
        "humidity": "High",
        "soil": "Orchid bark mix (no regular soil)",
        "fertilizer": "Weakly weekly (diluted fertilizer)",
        "common_problems": ["Root rot (overwater)", "No blooms (low light)"],
        "pests": ["Mealybugs", "Scale"],
        "pet_safety": "Generally safe",
        "care_tips": ["Clear pot helps monitor roots"]
    },

    "Parlor Palm (Chamaedorea elegans)": {
        "category": "Palm",
        "difficulty": "Easy",
        "light": "Low to medium indirect",
        "watering": {
            "frequency": "Weekly",
            "method": "Water when top soil dries",
            "notes": "Doesn’t like soggy soil"
        },
        "temperature": "18–26°C",
        "humidity": "Medium",
        "soil": "Well-draining",
        "fertilizer": "Monthly",
        "common_problems": ["Brown tips (dry air)", "Yellowing (overwatering)"],
        "pests": ["Spider mites"],
        "pet_safety": "Safe",
        "care_tips": ["Great low-light palm"]
    },

    "Peace lily": {
        "category": "Flowering foliage",
        "difficulty": "Medium",
        "light": "Low to medium indirect",
        "watering": {
            "frequency": "Weekly",
            "method": "Keep slightly moist",
            "notes": "Droops dramatically when thirsty"
        },
        "temperature": "18–27°C",
        "humidity": "High",
        "soil": "Rich, well-draining",
        "fertilizer": "Every 6 weeks",
        "common_problems": ["Brown tips (dry air)", "Yellow leaves (too wet)"],
        "pests": ["Fungus gnats", "Spider mites"],
        "pet_safety": "Toxic",
        "care_tips": ["Mist regularly", "Avoid direct sun"]
    },

    "Poinsettia (Euphorbia pulcherrima)": {
        "category": "Flowering seasonal",
        "difficulty": "Medium",
        "light": "Bright indirect",
        "watering": {
            "frequency": "When surface dries",
            "method": "Even moisture; do not waterlog",
            "notes": "Sensitive to drafts"
        },
        "temperature": "16–24°C",
        "humidity": "Medium",
        "soil": "Well-draining",
        "fertilizer": "Monthly after flowering",
        "common_problems": ["Leaf drop (draft/cold)", "Root rot (overwater)"],
        "pests": ["Whiteflies", "Mealybugs"],
        "pet_safety": "Toxic (mild to moderate)",
        "care_tips": ["12–14 hours darkness daily for re-bloom"]
    },

    "Polka Dot Plant (Hypoestes phyllostachya)": {
        "category": "Foliage",
        "difficulty": "Easy",
        "light": "Bright indirect",
        "watering": {
            "frequency": "2–3 times/week (keep moist)",
            "method": "Water when top starts drying",
            "notes": "Wilts quickly if dry"
        },
        "temperature": "18–27°C",
        "humidity": "Medium to high",
        "soil": "Well-draining",
        "fertilizer": "Monthly",
        "common_problems": ["Leggy growth (low light)", "Leaf drop (dry soil)"],
        "pests": ["Aphids"],
        "pet_safety": "Safe",
        "care_tips": ["Pinch tips to keep bushy"]
    },

    "Ponytail Palm (Beaucarnea recurvata)": {
        "category": "Succulent-like",
        "difficulty": "Easy",
        "light": "Bright light; some direct sun",
        "watering": {
            "frequency": "Every 3–4 weeks",
            "method": "Let soil dry completely",
            "notes": "Stores water in trunk"
        },
        "temperature": "18–30°C",
        "humidity": "Low",
        "soil": "Cactus mix",
        "fertilizer": "Every 2 months",
        "common_problems": ["Soft trunk (overwater)", "Brown tips (low light)"],
        "pests": ["Mealybugs"],
        "pet_safety": "Safe",
        "care_tips": ["Use small pot with drainage"]
    },

    "Pothos (Ivy arum)": {
        "category": "Trailing",
        "difficulty": "Very Easy",
        "light": "Low to bright indirect",
        "watering": {
            "frequency": "Every 1–2 weeks",
            "method": "Water when top soil dries",
            "notes": "Overwatering causes yellow leaves"
        },
        "temperature": "18–29°C",
        "humidity": "Medium",
        "soil": "Well-draining",
        "fertilizer": "Monthly",
        "common_problems": ["Leggy growth (low light)", "Yellow leaves (overwater)"],
        "pests": ["Mealybugs"],
        "pet_safety": "Toxic",
        "care_tips": ["Easy to propagate from cuttings"]
    },

    "Prayer Plant (Maranta leuconeura)": {
        "category": "Prayer plant",
        "difficulty": "Hard",
        "light": "Low to medium indirect",
        "watering": {
            "frequency": "Keep evenly moist",
            "method": "Use filtered water",
            "notes": "Hates dry soil"
        },
        "temperature": "18–26°C",
        "humidity": "High",
        "soil": "Peat-based airy mix",
        "fertilizer": "Monthly",
        "common_problems": ["Brown edges (dry air)", "Curling (dry soil)"],
        "pests": ["Spider mites"],
        "pet_safety": "Safe",
        "care_tips": ["High humidity is essential"]
    },

    "Rattlesnake Plant (Calathea lancifolia)": {
        "category": "Foliage",
        "difficulty": "Hard",
        "light": "Medium indirect",
        "watering": {
            "frequency": "Keep moist",
            "method": "Use filtered water",
            "notes": "Very humidity-dependent"
        },
        "temperature": "18–26°C",
        "humidity": "High",
        "soil": "Peat-based mix",
        "fertilizer": "Monthly",
        "common_problems": ["Brown tips (dry air)", "Curling (dry)"],
        "pests": ["Spider mites"],
        "pet_safety": "Safe",
        "care_tips": ["Humidifier recommended"]
    },

        "Rubber Plant (Ficus elastica)": {
        "category": "Tree foliage",
        "difficulty": "Easy",
        "light": "Bright indirect light",
        "watering": {
            "frequency": "Every 1–2 weeks",
            "method": "Water when top 5 cm of soil is dry",
            "notes": "Overwatering causes yellow leaves"
        },
        "temperature": "18–28°C",
        "humidity": "Medium",
        "soil": "Well-draining potting mix",
        "fertilizer": "Monthly during growing season",
        "common_problems": ["Leaf drop (stress)", "Yellow leaves (overwatering)"],
        "pests": ["Scale", "Spider mites"],
        "pet_safety": "Toxic",
        "care_tips": ["Wipe leaves regularly", "Avoid drafts"]
    },

    "Sago Palm (Cycas revoluta)": {
        "category": "Palm-like",
        "difficulty": "Medium",
        "light": "Bright indirect or some direct sun",
        "watering": {
            "frequency": "Every 2–3 weeks",
            "method": "Let soil dry between watering",
            "notes": "Extremely sensitive to overwatering"
        },
        "temperature": "18–30°C",
        "humidity": "Medium",
        "soil": "Fast-draining sandy soil",
        "fertilizer": "Palm fertilizer every 2 months",
        "common_problems": ["Yellow fronds (overwatering)", "Slow growth"],
        "pests": ["Scale"],
        "pet_safety": "Highly toxic",
        "care_tips": ["Very slow-growing", "Use heavy pot"]
    },

    "Schefflera": {
        "category": "Tree foliage",
        "difficulty": "Easy",
        "light": "Bright indirect",
        "watering": {
            "frequency": "Weekly",
            "method": "Water when top soil dries",
            "notes": "Avoid soggy soil"
        },
        "temperature": "18–27°C",
        "humidity": "Medium",
        "soil": "Well-draining potting soil",
        "fertilizer": "Monthly",
        "common_problems": ["Leaf drop (low light)", "Yellowing (overwatering)"],
        "pests": ["Spider mites", "Scale"],
        "pet_safety": "Toxic",
        "care_tips": ["Rotate for even growth"]
    },

    "Snake plant (Sanseviera)": {
        "category": "Succulent-like",
        "difficulty": "Very Easy",
        "light": "Low to bright indirect",
        "watering": {
            "frequency": "Every 3–4 weeks",
            "method": "Let soil dry fully",
            "notes": "Overwatering causes root rot"
        },
        "temperature": "15–30°C",
        "humidity": "Low",
        "soil": "Cactus/succulent mix",
        "fertilizer": "Every 2–3 months",
        "common_problems": ["Mushy leaves (overwatering)"],
        "pests": ["Spider mites"],
        "pet_safety": "Toxic",
        "care_tips": ["Perfect for beginners", "Air-purifying"]
    },

    "Tradescantia": {
        "category": "Trailing",
        "difficulty": "Easy",
        "light": "Bright indirect",
        "watering": {
            "frequency": "Weekly",
            "method": "Water when top soil dries",
            "notes": "Wilts quickly if dry"
        },
        "temperature": "18–27°C",
        "humidity": "Medium",
        "soil": "Well-draining",
        "fertilizer": "Monthly",
        "common_problems": ["Leggy growth (low light)"],
        "pests": ["Aphids"],
        "pet_safety": "Mildly toxic",
        "care_tips": ["Pinch tips to keep bushy"]
    },

    "Tulip": {
        "category": "Bulb flowering",
        "difficulty": "Easy",
        "light": "Bright light",
        "watering": {
            "frequency": "Moderate during growth",
            "method": "Keep soil lightly moist",
            "notes": "Reduce water after bloom"
        },
        "temperature": "10–18°C",
        "humidity": "Low",
        "soil": "Well-draining bulb mix",
        "fertilizer": "Bulb fertilizer during growth",
        "common_problems": ["Short bloom life indoors"],
        "pests": ["Aphids"],
        "pet_safety": "Toxic",
        "care_tips": ["Cool temperatures extend bloom"]
    },

    "Venus Flytrap": {
        "category": "Carnivorous",
        "difficulty": "Hard",
        "light": "Bright direct sunlight",
        "watering": {
            "frequency": "Keep soil constantly moist",
            "method": "Use distilled or rainwater only",
            "notes": "Never use tap water"
        },
        "temperature": "20–30°C (needs dormancy in winter)",
        "humidity": "High",
        "soil": "Peat moss + sand (no fertilizer)",
        "fertilizer": "None",
        "common_problems": ["Trap death (tap water)", "Weak traps (low light)"],
        "pests": ["Aphids"],
        "pet_safety": "Safe",
        "care_tips": ["Needs winter dormancy", "No regular soil"]
    },

    "Yucca": {
        "category": "Tree foliage",
        "difficulty": "Easy",
        "light": "Bright light; tolerates direct sun",
        "watering": {
            "frequency": "Every 2–3 weeks",
            "method": "Let soil dry well",
            "notes": "Drought tolerant"
        },
        "temperature": "18–30°C",
        "humidity": "Low",
        "soil": "Well-draining sandy soil",
        "fertilizer": "Monthly",
        "common_problems": ["Soft trunk (overwatering)"],
        "pests": ["Scale"],
        "pet_safety": "Toxic",
        "care_tips": ["Good for bright rooms"]
    },

    "ZZ Plant (Zamioculcas zamiifolia)": {
        "category": "Low light",
        "difficulty": "Very Easy",
        "light": "Low to bright indirect",
        "watering": {
            "frequency": "Every 3–4 weeks",
            "method": "Let soil dry completely",
            "notes": "Stores water in rhizomes"
        },
        "temperature": "18–30°C",
        "humidity": "Low",
        "soil": "Fast-draining potting soil",
        "fertilizer": "Every 2–3 months",
        "common_problems": ["Yellow leaves (overwatering)"],
        "pests": ["Mealybugs"],
        "pet_safety": "Toxic",
        "care_tips": ["Ideal office plant", "Very tolerant"]
    }
}
