"""
Bangladesh Land Records & Property Law Knowledge Base
Contains legal definitions, survey histories, e-Mutation workflows, land FAQs,
and Out-of-Scope Query Detection routines.
"""

import re

# Comprehensive Land Term Glossary
LAND_TERMS_GLOSSARY = {
    "khatian": {
        "keywords": ["khatian", "khatiyan", "khotiyan", "khotian", "khatain", "খতিয়ান"],
        "bn_title": "খতিয়ান (Khatian)",
        "definition": "জমিদার বা সরকারের অধীন কোনো স্বত্বাধিকারী বা প্রজার স্বত্ব, জমির পরিমাণ, অবস্থান ও দখল সংক্রান্ত তথ্যাবলি সংবলিত সরকারি বিবরণী।",
        "en_def": "Official record of land title detailing rights, owner names, land area, dag numbers, and possession status under government records."
    },
    "porcha": {
        "keywords": ["porcha", "porca", "purca", "purja", "পর্চা"],
        "bn_title": "পর্চা (Porcha)",
        "definition": "জরিপকালে প্রস্তুতকৃত খতিয়ানের খসড়া অনুলিপি যা স্বত্বাধিকারীকে যাচাই ও বিরোধ নিষ্পত্তির জন্য প্রদান করা হয়।",
        "en_def": "Draft copy of Khatian issued during field survey for owner verification and dispute resolution."
    },
    "dag_number": {
        "keywords": ["dag_number", "dag number", "dag", "dags", "plot number", "plot", "plots", "দাগ নম্বর", "দাগ"],
        "bn_title": "দাগ নম্বর (Plot Number)",
        "definition": "মৌজা নকশায় (Mouza Map) নির্দিষ্ট সীমানা দ্বারা চিহ্নিত প্রতিটি জমি বা ভূখণ্ডকে একটি ক্রমিক সংখ্যা দ্বারা চিহ্নিত করা হয়, একে দাগ নম্বর বলে।",
        "en_def": "Unique sequential number assigned to a specific parcel of land on a Mouza Map."
    },
    "mouza": {
        "keywords": ["mouza", "mauza", "mouzar", "mouzay", "মৌজা", "মৌজার"],
        "bn_title": "মৌজা (Mouza)",
        "definition": "ভূমি রাজস্ব আদায়ের মূল ভৌগোলিক ও প্রশাসনিক একক। প্রতিটি মৌজার একটি নির্দিষ্ট নাম ও জে.এল (JL) নম্বর থাকে।",
        "en_def": "Basic geographic and revenue administration unit. Every Mouza has a unique name and JL (Jurisdiction List) number."
    },
    "jl_number": {
        "keywords": ["jl_number", "jl number", "jl", "জে.এল", "জে এল"],
        "bn_title": "জে.এল নম্বর (JL Number)",
        "definition": "Jurisdiction List Number - থানা বা উপজেলার অধীনে মৌজার ভৌগোলিক অবস্থান নির্দেশক নির্দিষ্ট নম্বর।",
        "en_def": "Jurisdiction List Number - Specific numerical identifier assigned to a Mouza within a Thana/Upazila."
    },
    "namjari": {
        "keywords": ["namjari", "mutation", "নামজারি", "জমা-খারিজ", "জমা খারিজ"],
        "bn_title": "নামজারি বা জমা-খারিজ (Namjari / Mutation)",
        "definition": "ক্রয়, উত্তরাধিকার বা হস্তান্তরের মাধ্যমে জমির নতুন মালিকের নাম সরকারি খতিয়ানে অন্তর্ভুক্ত করা এবং পুরাতন মালিকের নাম খারিজ করার আইনি প্রক্রিয়া।",
        "en_def": "Official legal process of updating government record of rights to substitute the new owner's name in place of the former owner."
    },
    "dakhila": {
        "keywords": ["dakhila", "tax receipt", "khajna", "দাখিলা", "খাজনা"],
        "bn_title": "দাখিলা বা খাজনার রশিদ (Dakhila / Land Tax Receipt)",
        "definition": "ভূমি উন্নয়ন কর (খাজনা) পরিষদের পর সহকারী কমিশনার (ভূমি) কার্যালয় হতে প্রদত্ত সরকারি রসিদ।",
        "en_def": "Official government receipt issued upon payment of Land Development Tax."
    },
    "jamabandi": {
        "keywords": ["jamabandi", "জমাবন্দি", "জমা বন্দি"],
        "bn_title": "জমা বন্দি (Jamabandi)",
        "definition": "ভূমি মালিকের মোট কতটুকু জমি রয়েছে এবং বাৎসরিক কত টাকা খাজনা প্রযোজ্য তার রেজিস্টার।",
        "en_def": "Register maintained by Land Revenue Office recording land holdings and assessed tax payable."
    }
}

# Survey Types & Histories in Bangladesh
SURVEY_HISTORIES = {
    "CS": {
        "name": "CS Survey (Cadastral Survey)",
        "period": "1888 - 1940",
        "bn_desc": "ভারত উপমহাদেশের প্রথম বৈজ্ঞানিক ভূমি জরিপ। এটি ভারত ভূখণ্ডে স্বত্ব ও মালিকানার মূল ভিত্তিমূল হিসেবে গণ্য হয়।",
        "en_desc": "First scientific land survey conducted under the Bengal Tenancy Act 1885. Serves as the primary legal origin of land ownership in Bangladesh.",
        "legal_status": "মালিকানার মূল উৎস প্রমাণের জন্য আদালতে সিএস খতিয়ান প্রধান সাক্ষ্য হিসেবে গণ্য হয়।"
    },
    "SA": {
        "name": "SA Survey (State Acquisition Survey)",
        "period": "1956 - 1965",
        "bn_desc": "১৯৫০ সালের প্রজা স্বত্ব অধিগ্রহণ আইনের পর জমিদারি প্রথা বিলুপ্ত হলে জমিদারের অধীনে থাকা স্বত্ব সরাসরি সরকারের অধীনে আনার জন্য এ জরিপ করা হয়।",
        "en_desc": "Conducted following the State Acquisition and Tenancy Act 1950 after the abolition of the Zamindari system.",
        "legal_status": "জমিদারি বিলোপ পরবর্তী সরকারি রেজিস্টার ও খতিয়ান।"
    },
    "RS": {
        "name": "RS Survey (Revisional Survey)",
        "period": "1965 - 1990",
        "bn_desc": "সিএস ও এসএ জরিপের ভুলত্রুটি সংশোধন এবং বাস্তব দখলের ভিত্তিতে তৈরি করা অত্যন্ত নির্ভরযোগ্য জরিপ।",
        "en_desc": "Revisional survey conducted to correct errors in CS and SA surveys based on actual field possession and deeds.",
        "legal_status": "বর্তমান বিরোধ নিষ্পত্তিতে বিএস জরিপ না হওয়া এলাকাগুলোতে আরএস জরিপ সর্বোচ্চ প্রাধান্য পায়।"
    },
    "BS": {
        "name": "BS / BRS Survey (Bangladesh Survey)",
        "period": "1990 - চলমান (Present)",
        "bn_desc": "স্বাধীন বাংলাদেশের আধুনিকতম ভূমি জরিপ। এতে আধুনিক প্রযুক্তি ও ডিজিটাল ম্যাপ ব্যবহার করা হচ্ছে।",
        "en_desc": "Latest modern land survey conducted in independent Bangladesh using modern technology and digital maps.",
        "legal_status": "যেসব এলাকায় বিএস চূড়ান্তভাবে প্রকাশিত হয়েছে, সেখানে বর্তমানে বিএস খতিয়ানই চূড়ান্ত গ্রহণযোগ্য।"
    }
}

# e-Mutation (ই-নামজারি) Step-by-Step Guide
NAMJARI_GUIDE = {
    "portal": "https://mutations.land.gov.bd",
    "official_fee_bdt": None,  # Fees require live verification before quoting
    "fee_breakdown": [
        "সরকারি ফি, সেবার শর্ত ও সময়সীমা পরিবর্তিত হতে পারে; আবেদন করার সময় সংশ্লিষ্ট সরকারি পোর্টাল থেকে বর্তমান তথ্য যাচাই করুন।"
    ],
    "required_documents": [
        "মালিকানার দলিল (Deed of Purchase / Gift / Partition)",
        "সর্বশেষ খতিয়ান (CS/RS/SA/BS Khatian Copy)",
        "সর্বশেষ খাজনার দাখিলা (Updated Land Development Tax Receipt)",
        "ওয়ারিশ সনদ (উত্তরাধিকার সূত্রের ক্ষেত্রে - Succession Certificate)",
        "আবেদনকারীর জাতীয় পরিচয়পত্র (NID) ও মোবাইল নম্বর"
    ],
    "steps": [
        "১. www.mutations.land.gov.bd পোর্টালে গিয়ে জাতীয় পরিচয়পত্র ও মোবাইল নম্বর দিয়ে নামজারি আবেদন সাবমিট করুন।",
        "২. প্রয়োজনীয় দলিলপত্র ও সর্বশেষ খাজনার রসিদ আপলোড করুন; ফি থাকলে বর্তমান সরকারি পোর্টালে যাচাই করে পরিশোধ করুন।",
        "৩. সহকারী কমিশনার (ভূমি) কার্যালয় থেকে প্রাথমিক যাচাই শেষে নোটিশ ইস্যু করা হবে।",
        "৪. ইউনিয়ন ভূমি উপ-সহকারী কর্মকর্তা (তহশিলদার) সরেজমিনে তদন্ত প্রতিবেদন জমা দেবেন।",
        "৫. আবেদন অনুমোদিত হলে নির্দেশনা অনুযায়ী প্রযোজ্য DCR ফি যাচাই করে পরিশোধ করুন।",
        "৬. অনলাইনে কিউআর কোড সংবলিত ই-নামজারি খতিয়ান ও ডি সি আর ডাউনলোড করে প্রিন্ট করুন।"
    ],
    "timeframe_days": "বর্তমান সময়সীমা সংশ্লিষ্ট সরকারি পোর্টাল থেকে যাচাই করুন"
}

# Land Legal & Discrepancy FAQs
LAND_LEGAL_FAQS = [
    {
        "keywords": ["cs", "rs", "মিল নাই", "পার্থক্য", "discrepancy", "diff", "অমিল"],
        "question": "সিএস (CS) এবং আরএস (RS) খতিয়ানে মিল না থাকলে কি করণীয়?",
        "answer": "সিএস ও আরএস খতিয়ানে অমিল থাকলে:\n১. মালিকানার ধারাবাহিকতা (Chain of Ownership) যাচাই করতে মধ্যবর্তী এসএ (SA) খতিয়ান ও হস্তান্তরের দলিলসমূহ পরীক্ষা করুন।\n২. যদি ভুলবশত আরএস খতিয়ানে নাম বাদ পড়ে থাকে, তবে এসএসিআই (State Acquisition & Tenancy Act) ধারা ১৪৩/১৪৯ অনুযায়ী সহকারী কমিশনার (ভূমি) কার্যালয়ে মিস কেস (Miss Case) আবেদন করুন।\n৩. দেওয়ানি আদালতে স্বত্ব ঘোষণার মামলা (Title Suit) দায়ের করে খতিয়ান সংশোধনের ডিগ্রি নেওয়া যেতে পারে।"
    },
    {
        "keywords": ["ভুল", "সংশোধন", "correct", "correction", "mistake"],
        "question": "খতিয়ানে নাম বা জমির পরিমাণে ভুল থাকলে কিভাবে সংশোধন করবেন?",
        "answer": "খতিয়ান সংশোধনের উপায়:\n১. **প্রিন্টিং বা সাধারণ ক্ল্যারিক্যাল ভুল:** সহকারী কমিশনার (ভূমি) কার্যালয়ে প্রজাস্বত্ব বিধিমালা অনুযায়ী সংশোধনের আবেদন করতে হবে।\n২. **মালিকানা সংক্রান্ত বড় জটিলতা:** সহকারী কমিশনার (ভূমি) কার্যালয়ে মিস কেস বা বিজ্ঞ ল্যান্ড সার্ভে ট্রাইব্যুনালে (Land Survey Tribunal) মামলা দায়ের করতে হবে।"
    },
    {
        "keywords": ["দলিল", "খতিয়ান", "deed", "versus", "তাফাত", "কোন্টা বড়"],
        "question": "দলিল এবং খতিয়ানের মধ্যে কোনটি বেশি গুরুত্বপূর্ণ?",
        "answer": "দলিল হলো মালিকানা হস্তান্তরের প্রমাণ (Proof of Ownership Transfer), আর খতিয়ান হলো সরকারের রাজস্ব খাতায় দখলি স্বত্বের রেকর্ড (Record of Rights).\n- শুধু দলিল থাকলেও নামজারি খতিয়ান না করা পর্যন্ত সরকারি রেকর্ডে আপনার নাম উঠবে না এবং জমি বিক্রি বা ঋণ নেওয়া যাবে না।\n- তাই দলিল সম্পাদনের পরপরই ই-নামজারি সম্পন্ন করা আবশ্যক।"
    }
]

# Non-Land Topics for Out-Of-Scope Detection
NON_LAND_TOPICS = [
    r'\b(recipe|cooking|biryani|pasta|pizza|cake|cook|kitchen)\b',
    r'\b(python|javascript|java|c\+\+|coding|react|html|css|bug|code|script|software)\b',
    r'\b(cricket|football|messi|ronaldo|ipl|world cup|match|player|stadium)\b',
    r'\b(movie|cinema|song|music|hollywood|bollywood|actor|actress|video)\b',
    r'\b(weather|forecast|rain|temperature|climate|sunshine)\b',
    r'\b(calculus|algebra|physics|chemistry|biology|quantum)\b',
    r'\b(who is president of|currency of|mount everest|capital of france)\b'
]

# Land Specific Domain Keywords
LAND_DOMAIN_KEYWORDS = [
    'khatian', 'khatiyan', 'khotiyan', 'khotian', 'khatain', 'khatianer', 'khatiyaner', 'khotiyaner',
    'porcha', 'porca', 'purca', 'purja', 'mouza', 'mauza', 'mouzar', 'mouzay', 'mauzar',
    'dag', 'dags', 'dager', 'dagno', 'dagnumber', 'plot', 'plots', 'plotno',
    'survey', 'cs', 'rs', 'sa', 'bs', 'brs', 'namjari', 'mutation', 'dakhila', 'khajna', 'tax', 'deed', 'dolil', 'jamabandi', 'jomabandi',
    'land', 'property', 'owner', 'malik', 'malikana', 'maliker', 'jomi', 'jomir', 'jomijama', 'jomidari', 'jaga', 'jagir', 'bhumi', 'bhumir',
    'upazila', 'upazilar', 'upazilay', 'district', 'district-er', 'zila', 'zilar', 'zilay', 'thana', 'thanar',
    'brahmanbaria', 'sarail', 'bhandaria', 'nabinagar', 'nasirnagar', 'ashuganj', 'pirojpur', 'barguna', 'barisal', 'rajshahi', 'dhaka',
    'details', 'info', 'khobor', 'tathya', 'tottho', 'dakhaw', 'dekhao', 'dekhun', 'daow', 'dao', 'din', 'bhasha', 'bolo', 'bolun',
    'kothay', 'kar', 'kaam', 'kine', 'karer', 'khuje', 'khujun', 'koto', 'kototuk', 'ache', 'achhe', 'ase', 'nai', 'nei', 'chai', 'list', 'sob',
    'জমাবন্দি', 'খতিয়ান', 'খতিয়ানের', 'পর্চা', 'দাগ', 'দাগের', 'মৌজা', 'মৌজার', 'সার্ভে', 'নামজারি', 'জমি', 'জমির', 'জমিজমা', 'ভূমি',
    'মালিক', 'মালিকের', 'মালিকানা', 'খাজনা', 'দাখিলা', 'দলিল', 'উপজেলা', 'উপজেলায়', 'জেলা', 'জেলায়', 'ব্রাহ্মণবাড়িয়া', 'সরাইল', 'ভাট',
    'কাংশা', 'সাদকপুর', 'পরিমাণ', 'কোথায়', 'কার', 'কতো', 'কতোটুকু', 'লিস্ট', 'আছে', 'নাই', 'নেই', 'সংশোধন', 'অমিল', 'আইন', 'ফি', 'আবেদন'
]

def is_out_of_scope(query):
    """
    Check if user query is completely unrelated to land, property, real estate,
    or Bangladesh administration. Only rejects explicit non-land topics.
    """
    query_lower = query.lower().strip()
    
    # Very short conversational queries are always in scope
    greetings = ['hi', 'hello', 'hey', 'سلام', 'আসসালামু আলাইকুম', 'নমস্কার', 'কেমন আছেন', 'help']
    if any(g == query_lower for g in greetings) or len(query_lower) < 4:
        return False, None

    # Check against explicit non-land topics ONLY
    for pattern in NON_LAND_TOPICS:
        if re.search(pattern, query_lower, re.IGNORECASE):
            return True, {
                "reason": "Non-land topic detected",
                "suggested_topics": [
                    "খতিয়ান ও মালিকানার তথ্য অনুসন্ধান (e.g. 'ভাট বাড়িয়া মৌজার খতিয়ান ৩ এর মালিক কে?')",
                    "ই-নামজারি (e-Mutation) আবেদন নিয়ম ও ফি",
                    "সিএস, আরএস ও বিএস সার্ভের পার্থক্য",
                    "খতিয়ান ভুল সংশোধনের আইনি উপায়"
                ]
            }

    # All Bengali or Banglish queries defaults to in-scope
    return False, None


def retrieve_relevant_knowledge(query):
    """
    Search domain knowledge base for legal/procedural information matching query terms.
    """
    query_lower = query.lower()
    matches = []

    # 1. Check Survey Types
    for survey_code, info in SURVEY_HISTORIES.items():
        if survey_code.lower() in query_lower or info['name'].lower() in query_lower:
            matches.append(f"### 📌 {info['name']} ({info['period']})\n- **বর্ণনা:** {info['bn_desc']}\n- **আইনি মর্যাদা:** {info['legal_status']}")

    # 2. Check e-Mutation
    if any(k in query_lower for k in ['namjari', 'mutation', 'নামজারি', 'জমা খারিজ', 'অনলাইন আবেদন', 'ফি']):
        matches.append(
            f"### 📝 ই-নামজারি (e-Mutation) তথ্যাবলি\n"
            f"- **অফিসিয়াল পোর্টাল:** {NAMJARI_GUIDE['portal']}\n"
            "- **সরকারি ফি:** বর্তমান সরকারি ফি ও সময়সীমা আবেদন পোর্টালে যাচাই করুন; এই অ্যাপ লাইভ ফি নিশ্চিত করে না।\n"
            f"- **ফি এর বিবরণ:** {', '.join(NAMJARI_GUIDE['fee_breakdown'])}\n"
            f"- **প্রয়োজনীয় কাগজপত্র:** {', '.join(NAMJARI_GUIDE['required_documents'])}\n"
            f"- **আবেদনের নিয়ম:**\n" + "\n".join(NAMJARI_GUIDE['steps'])
        )

    # 3. Check FAQs & Legal Remedies
    for faq in LAND_LEGAL_FAQS:
        if any(kw in query_lower for kw in faq['keywords']):
            matches.append(f"### ⚖️ {faq['question']}\n{faq['answer']}")

    # 4. Check Glossary terms
    for key, item in LAND_TERMS_GLOSSARY.items():
        kws = item.get("keywords", [key])
        if any(kw in query_lower for kw in kws):
            matches.append(f"### 📖 {item['bn_title']}\n{item['definition']}\n*English:* {item['en_def']}")

    return "\n\n".join(matches) if matches else ""
