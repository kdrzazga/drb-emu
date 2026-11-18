FIRST_NAMES = (
    "Anna", "Piotr", "Katarzyna", "Tomasz", "Magdalena", "Michał", "Agnieszka", "Krzysztof", "Joanna", "Paweł",
    "Ewa", "Marcin", "Natalia", "Jakub", "Zofia", "Łukasz", "Maria", "Adam", "Julia", "Marek",
    "Emma", "Liam", "Olivia", "Noah", "Sophie", "Lukas", "Hannah", "Felix", "Lena", "Jonas",
    "Charlotte", "Oliver", "Amelia", "George", "Isla", "Harry", "Elena", "Mateo", "Lucia", "Hugo",
)

LAST_NAMES = (
    "Nowak", "Kowalski", "Wiśniewski", "Wójcik", "Kowalczyk", "Kamiński", "Lewandowski", "Zieliński", "Szymański", "Woźniak",
    "Dąbrowski", "Kozłowski", "Jankowski", "Mazur", "Kwiatkowski", "Krawczyk", "Piotrowski", "Grabowski", "Pawłowski", "Michalski",
    "Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner", "Becker", "Smith", "Jones",
    "Taylor", "Brown", "Williams", "Wilson", "Johnson", "Davies", "Novák", "Svoboda", "Horváth", "Rossi",
)

STREETS = {
    "PL": ("ul. Marszałkowska", "ul. Długa", "ul. Polna", "ul. Leśna", "ul. Słoneczna", "ul. Szkolna", "ul. Ogrodowa", "ul. Lipowa",
           "ul. Mickiewicza", "ul. Kościuszki", "ul. Piłsudskiego", "ul. Sienkiewicza"),
    "DE": ("Hauptstraße", "Bahnhofstraße", "Gartenstraße", "Schillerstraße", "Lindenallee"),
    "GB": ("High Street", "Station Road", "Church Lane", "Park Avenue", "Mill Road"),
    "CZ": ("Národní", "Vodičkova", "Karlova", "Husova"),
    "AT": ("Ringstraße", "Kärntner Straße", "Mariahilfer Straße"),
}

CITIES = (
    ("Warszawa", "PL"), ("Kraków", "PL"), ("Wrocław", "PL"), ("Gdańsk", "PL"), ("Poznań", "PL"), ("Łódź", "PL"),
    ("Katowice", "PL"), ("Lublin", "PL"), ("Szczecin", "PL"), ("Berlin", "DE"), ("Hamburg", "DE"), ("München", "DE"),
    ("London", "GB"), ("Manchester", "GB"), ("Praha", "CZ"), ("Wien", "AT"),
)

POLISH_CITY_WEIGHT = 4

COMPANY_FIRST_WORDS = (
    "Vistula", "Baltic", "Silesian", "Nordic", "Orion", "Atlas", "Polaris", "Carpathian", "Amber", "Iron",
    "Granite", "Falcon", "Summit", "Horizon", "Meridian", "Pioneer", "Crystal", "Oak", "Riverside", "Northern",
)

COMPANY_SECOND_WORDS = (
    ("Logistics", "Transport"), ("Steel", "Manufacturing"), ("Software", "IT"), ("Foods", "Food"), ("Energy", "Energy"),
    ("Construction", "Construction"), ("Textiles", "Manufacturing"), ("Pharma", "Healthcare"), ("Media", "Media"),
    ("Motors", "Automotive"), ("Electronics", "Electronics"), ("Chemicals", "Chemicals"), ("Consulting", "Services"),
    ("Retail", "Retail"), ("Agro", "Agriculture"), ("Systems", "IT"), ("Paper", "Manufacturing"), ("Shipping", "Transport"),
)

LEGAL_FORMS = {
    "PL": ("Sp. z o.o.", "S.A."),
    "DE": ("GmbH", "AG"),
    "GB": ("Ltd", "PLC"),
    "CZ": ("s.r.o.", "a.s."),
    "AT": ("GmbH",),
}
