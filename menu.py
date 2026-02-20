MENU = [
    # Standardpizzor (100 kr)
    {"nr": 1,  "name": "Margareta",          "desc": "Ost",                                                    "price": 100, "cat": "Standard"},
    {"nr": 2,  "name": "Vesuvio",            "desc": "Skinka",                                                 "price": 100, "cat": "Standard"},
    {"nr": 3,  "name": "Paula",              "desc": "Champinjoner, köttfärssås",                              "price": 100, "cat": "Standard"},
    {"nr": 4,  "name": "Capricciosa",        "desc": "Skinka, champinjoner",                                   "price": 100, "cat": "Standard"},
    {"nr": 5,  "name": "Altonno",            "desc": "Tonfisk",                                                "price": 100, "cat": "Standard"},
    {"nr": 6,  "name": "Hawaii",             "desc": "Skinka, ananas",                                         "price": 100, "cat": "Standard"},
    {"nr": 7,  "name": "Buruna",             "desc": "Champinjoner",                                           "price": 100, "cat": "Standard"},
    {"nr": 8,  "name": "Bussola",            "desc": "Skinka, räkor",                                          "price": 100, "cat": "Standard"},
    {"nr": 9,  "name": "Opera",              "desc": "Skinka, tonfisk",                                        "price": 100, "cat": "Standard"},
    {"nr": 10, "name": "Orientale",          "desc": "Köttfärssås",                                            "price": 100, "cat": "Standard"},
    {"nr": 11, "name": "Vera",               "desc": "Skinka, färska tomater",                                 "price": 100, "cat": "Standard"},
    {"nr": 12, "name": "Tropicana",          "desc": "Skinka, ananas, banan, curry",                           "price": 105, "cat": "Standard"},
    {"nr": 13, "name": "Marinara",           "desc": "Räkor, musslor",                                         "price": 105, "cat": "Standard"},
    {"nr": 14, "name": "Gondola",            "desc": "Räkor, champinjoner",                                    "price": 105, "cat": "Standard"},
    {"nr": 15, "name": "Bussola Special",    "desc": "Skinka, räkor, ananas",                                  "price": 105, "cat": "Standard"},
    {"nr": 16, "name": "Campagnola",         "desc": "Salami, lök",                                            "price": 105, "cat": "Standard"},
    {"nr": 17, "name": "Balanzone",          "desc": "Skinka, salami",                                         "price": 105, "cat": "Standard"},
    {"nr": 18, "name": "Pazza",              "desc": "Räkor, champinjoner, paprika, lök",                      "price": 105, "cat": "Standard"},
    {"nr": 19, "name": "Vegetale",           "desc": "Champinjoner, paprika, oliver, lök",                     "price": 105, "cat": "Standard"},
    {"nr": 20, "name": "Vegetale Special",   "desc": "Champinjoner, fårost, paprika, oliver, lök",             "price": 105, "cat": "Standard"},
    {"nr": 21, "name": "Diabolo",            "desc": "Skinka, köttfärssås",                                    "price": 105, "cat": "Standard"},
    {"nr": 22, "name": "Primavera",          "desc": "Bacon, ägg, lök",                                        "price": 105, "cat": "Standard"},
    {"nr": 23, "name": "Romana",             "desc": "Skinka, champinjoner, räkor",                             "price": 105, "cat": "Standard"},
    {"nr": 24, "name": "Orientale Special",  "desc": "Champinjoner, köttfärssås, ägg",                         "price": 105, "cat": "Standard"},
    {"nr": 25, "name": "Rimini",             "desc": "Skinka, räkor, crab-fish",                                "price": 105, "cat": "Standard"},
    {"nr": 26, "name": "Bolognese",          "desc": "Skinka, champinjoner, köttfärssås",                      "price": 105, "cat": "Standard"},
    {"nr": 27, "name": "Venezia",            "desc": "Skinka, räkor, tonfisk",                                 "price": 105, "cat": "Standard"},
    {"nr": 28, "name": "Pronto",             "desc": "Skinka, fefferoni, lök",                                 "price": 105, "cat": "Standard"},
    {"nr": 29, "name": "Carbonara",          "desc": "Skinka, champinjoner, paprika, lök",                     "price": 105, "cat": "Standard"},
    {"nr": 30, "name": "La Gonzola",         "desc": "Skinka, ädelost",                                        "price": 105, "cat": "Standard"},

    # Inbakade pizzor (110 kr)
    {"nr": 31, "name": "Calzone",            "desc": "Inbakad, skinka",                                        "price": 110, "cat": "Inbakad"},
    {"nr": 32, "name": "Calzone Special",    "desc": "Inbakad, skinka, räkor",                                 "price": 110, "cat": "Inbakad"},
    {"nr": 33, "name": "La Polarde",         "desc": "Inbakad, skinka, ädelost, crème fraiche",                "price": 110, "cat": "Inbakad"},

    # Specialpizzor (115 kr)
    {"nr": 34, "name": "Sorrento",           "desc": "Köttfärssås, lök, fefferoni, tomater, stark sås",        "price": 115, "cat": "Special"},
    {"nr": 35, "name": "Marco Polo",         "desc": "Skinka, räkor, champinjoner, tonfisk",                   "price": 115, "cat": "Special"},
    {"nr": 36, "name": "Quattro Stagioni",   "desc": "Skinka, räkor, champinjoner, musslor, kronärtskocka",    "price": 115, "cat": "Special"},
    {"nr": 37, "name": "Las Vegas",          "desc": "Skinka, champinjoner, bacon, ägg, lök",                  "price": 115, "cat": "Special"},
    {"nr": 38, "name": "Fantasia",           "desc": "Skinka, salami, bacon, lök",                             "price": 115, "cat": "Special"},
    {"nr": 39, "name": "Maxhot",             "desc": "Stark korv, champinjoner, fefferoni, lök, stark sås",    "price": 115, "cat": "Special"},
    {"nr": 40, "name": "Frutti di Mare",     "desc": "Räkor, tonfisk, musslor, crab-fish",                     "price": 115, "cat": "Special"},
    {"nr": 41, "name": "Mamma Mia",          "desc": "Köttfärssås, lök, fefferoni, bearnaisesås",              "price": 115, "cat": "Special"},
    {"nr": 42, "name": "La Casa",            "desc": "Skinka, räkor, champinjoner, köttfärssås",               "price": 115, "cat": "Special"},

    # Kebabpizzor — halvinbakade (115 kr)
    {"nr": 43, "name": "Caruso",             "desc": "Kebabkött, champinjoner, vitlök",                        "price": 115, "cat": "Kebab"},
    {"nr": 44, "name": "Riviera",            "desc": "Kebabkött, champinjoner, tomater, fefferoni",            "price": 115, "cat": "Kebab"},
    {"nr": 45, "name": "San Remo",           "desc": "Kebabkött, tomater, stark sås",                          "price": 115, "cat": "Kebab"},
    {"nr": 46, "name": "Bella",              "desc": "Kebabkött, svamp, vitlök, bearnaise, fefferoni",         "price": 115, "cat": "Kebab"},
    {"nr": 47, "name": "Verona",             "desc": "Kebabkött, lök, tomater, paprika, fefferoni",            "price": 115, "cat": "Kebab"},

    # Kycklingpizzor — halvinbakade (115 kr)
    {"nr": 48, "name": "Regina",             "desc": "Kyckling, ananas, curry",                                "price": 115, "cat": "Kyckling"},
    {"nr": 49, "name": "Ancona",             "desc": "Kyckling, banan, curry",                                 "price": 115, "cat": "Kyckling"},
    {"nr": 50, "name": "Blanca",             "desc": "Kyckling, bearnaisesås",                                 "price": 115, "cat": "Kyckling"},
    {"nr": 51, "name": "Udine",              "desc": "Kyckling, champinjoner, vitlök, bearnaisesås, fefferoni","price": 115, "cat": "Kyckling"},

    # Fläskfilépizzor (120 kr)
    {"nr": 52, "name": "Roma",               "desc": "Fläskfilé, bearnaisesås (halvinbakad)",                  "price": 120, "cat": "Fläskfilé"},
    {"nr": 53, "name": "Farma",              "desc": "Fläskfilé, champinjoner, lök, fefferoni",                "price": 120, "cat": "Fläskfilé"},
    {"nr": 54, "name": "La Luna",            "desc": "Fläskfilé, champinjoner, vitlök, bearnaisesås",          "price": 120, "cat": "Fläskfilé"},
    {"nr": 55, "name": "Napoli",             "desc": "Fläskfilé, bacon, ägg, champinjoner",                    "price": 120, "cat": "Fläskfilé"},

    # Oxfilépizzor (130 kr)
    {"nr": 56, "name": "Ciao Ciao",          "desc": "Oxfilé, bearnaisesås (halvinbakad)",                     "price": 130, "cat": "Oxfilé"},
    {"nr": 57, "name": "Madonna",            "desc": "Oxfilé, champinjoner, lök, fefferoni (halvinbakad)",     "price": 130, "cat": "Oxfilé"},
    {"nr": 58, "name": "Huset Special",      "desc": "Oxfilé, champinjoner, vitlök, bearnaisesås",             "price": 130, "cat": "Oxfilé"},
    {"nr": 59, "name": "Malaja",             "desc": "Oxfilé, lök, tomater, svartpeppar",                      "price": 130, "cat": "Oxfilé"},
    {"nr": 60, "name": "La Bamba",           "desc": "Oxfilé, bacon, ägg, champinjoner, fefferoni",            "price": 140, "cat": "Oxfilé"},
    {"nr": 61, "name": "Bergmans Special",   "desc": "Oxfilé, köttfärssås, skinka, räkor, fefferoni, bearnaisesås", "price": 140, "cat": "Oxfilé"},
    {"nr": 62, "name": "Ali Baba",           "desc": "Oxfilé, ädelost, färska tomater, bearnaisesås",          "price": 140, "cat": "Oxfilé"},
    {"nr": 63, "name": "Lady Diana",         "desc": "Oxfilé, skinka, lök, färska tomater, vitlök, bearnaisesås", "price": 140, "cat": "Oxfilé"},
    {"nr": 64, "name": "Atlantic",           "desc": "Oxfilé, ädelost, lök, svamp, bearnaisesås",              "price": 140, "cat": "Oxfilé"},
    {"nr": 65, "name": "Dormiro",            "desc": "Oxfilé, svamp, banan, curry, bearnaisesås",              "price": 140, "cat": "Oxfilé"},

    # Mexikanska pizzor (115 kr)
    {"nr": 66, "name": "Mexicana",           "desc": "Skinka, tomater, tacosås, taco kryddmix, jalapeño",      "price": 115, "cat": "Mexikansk"},
    {"nr": 67, "name": "Monterrey",          "desc": "Köttfärssås, tacosås, taco kryddmix, vitlök, stark sås", "price": 115, "cat": "Mexikansk"},
    {"nr": 68, "name": "Sierra",             "desc": "Köttfärssås, champinjoner, jalapeño, taco kryddmix, bearnaisesås", "price": 115, "cat": "Mexikansk"},
    {"nr": 69, "name": "Mérida",             "desc": "Kebab, fefferoni, jalapeño, taco kryddmix, bearnaisesås","price": 115, "cat": "Mexikansk"},
    {"nr": 70, "name": "Mexikansk Special",  "desc": "Kyckling, jalapeño, taco kryddmix, tacosås",             "price": 115, "cat": "Mexikansk"},
    {"nr": 71, "name": "Acapulco",           "desc": "Räkor, köttfärs, jalapeño, lök, tacosås, vitlökssås",    "price": 115, "cat": "Mexikansk"},
]

MENU_BY_NR = {p["nr"]: p for p in MENU}

CATEGORIES = [
    "Standard", "Inbakad", "Special", "Kebab",
    "Kyckling", "Fläskfilé", "Oxfilé", "Mexikansk",
]


def menu_as_text():
    """Return menu formatted for OpenAI instructions."""
    lines = ["Alla pizzor innehåller tomatsås och ost.\n"]
    current_cat = None
    for p in MENU:
        if p["cat"] != current_cat:
            current_cat = p["cat"]
            lines.append(f"\n--- {current_cat}pizzor ---")
        lines.append(f"{p['nr']}. {p['name']} ({p['price']} kr) — {p['desc']}")
    return "\n".join(lines)
