import re
import json
import random
import requests
from typing import List, Dict, Any, Optional
from .config import load_settings


NICHE_VISUAL_FLAVORS = {
    "Military & Defense": ["military armed soldiers tactical", "combat battlefield explosion smoke", "military aircraft fighter jet", "war tank armored vehicle", "tactical air defense radar", "military armed convoy patrol"],
    "War & Conflict": ["war explosion battlefield smoke", "combat soldiers tactical firing", "military airstrike fighter jet", "artillery tank combat", "military base surveillance"],
    "Motivation Psychology": ["athlete training gym sweat", "running sunrise outdoor dawn", "determined person climbing mountain summit", "focused entrepreneur modern skyscraper", "lone figure ocean cliff dramatic", "heavy barbell lifting gym focus", "person washing face cold water morning"],
    "Nature & Wildlife": ["majestic aerial landscape 4k", "dense emerald forest mist", "mountain waterfall scenic", "wild ocean waves sunset", "sunrise clouds timelapse"],
    "Tech & AI": ["futuristic server room glowing", "cyberpunk holographic data", "artificial intelligence robotic hand", "modern high tech workspace", "digital code matrix"],
    "Finance & Wealth": ["luxury skyscraper trading floor", "businessman counting money cash", "stock market chart ticker green", "private jet luxury lifestyle", "financial district wall street"],
    "Luxury & Lifestyle": ["supercar driving coastline sunset", "luxury modern penthouse view", "rolex watch diamond elegance", "champagne toast high society", "yacht ocean cruising"],
    "Fitness & Health": ["athlete training gym sweat", "running sunrise outdoor trail", "heavy barbell lifting focus", "healthy organic meal prep", "athletic silhouette sprint"],
    "Stoicism & Philosophy": ["ancient marble statue portrait", "lone figure standing ocean cliff", "stormy clouds dramatic sky", "candle burning dark room", "calm warrior meditation"],
    "Sci-Fi & Space": ["deep space galaxy nebula", "astronaut walking planet surface", "hubble telescope cosmos 4k", "spacewalk earth orbit satellite", "futuristic sci-fi spacecraft"],
    "Crime & Mystery": ["foggy night city street rain", "detective silhouette crime scene", "vintage typewriter noir mystery", "shadowy figure suspense corridor", "police siren night moody"],
    "Meditation & Lofi": ["calm peaceful water ripples", "zen bamboo garden soft light", "candle flame soft glow", "cozy rain window lofi room", "serene misty lake reflection"],
    "Brain & Human Facts": ["human brain glowing neural network", "optical illusion rotating abstract", "curious person thinking portrait", "dna double helix molecular", "complex clockwork gears mechanism"],
    "History & Empires": ["ancient roman colosseum aerial", "egyptian pyramids golden sunset", "medieval stone castle fortress", "ancient parchment map candle", "classical antique temple ruins"],
    "Business & Hustle": ["modern glass office boardroom", "young startup founders whiteboard", "confident ceo presentation", "busy corporate financial district", "laptop typing analytics charts"],
    "Automotive & Supercars": ["matte black supercar drifting track", "formula 1 race car speed blur", "engine pistons mechanical combustion", "luxury sports car cockpit interior", "night highway speed light trails"],
    "Gaming & Esports": ["cyberpunk gamer room neon rgb", "esports tournament crowd cheering", "futuristic mechanical robot gaming", "retro arcade machines glowing", "virtual reality gamer headset"],
    "Travel & Adventure": ["tropical beach turquoise water drone", "swiss alps snow peaks aerial", "wandering ancient european alley", "hiking backpacker mountain ridge", "traditional asian lantern temple"],
    "Science & Engineering": ["scientific laboratory beaker chemicals", "quantum physics particle collision", "laser beam laboratory precision", "robotic automated assembly arm", "microscope view living cells"],
    "Productivity & Self-Growth": ["minimalist clean wooden desk morning", "writing journal fountain pen coffee", "person meditating sunrise balcony", "organized bookshelf books library", "early morning focused study"],
    "Horror & Paranormal": ["eerie abandoned house mist", "creepy shadows dark woods night", "flickering hallway light bulb", "silhouette foggy graveyard trees", "mysterious glowing portal night"],
    "Food & Culinary": ["chef slicing gourmet steak flame", "artisanal coffee pour over barista", "fresh organic vegetables farm", "wood fired pizza oven crust", "delicious chocolate dessert drizzle"],
    "Wildlife Predators & Oceans": ["lion pride golden savannah hunting", "great white shark underwater coral", "eagle soaring mountain thermals", "orca killer whale ocean breach", "jaguar stalking rainforest river"],
    "General": ["cinematic inspiring 4k", "dramatic lighting cinematic", "people lifestyle urban", "beautiful scenery landscape"]
}


KEYWORD_MAP = {
    "tired": ["exhausted man sitting desk", "tired worker walking home", "overworked person head in hands"],
    "sleep": ["person sleeping bed night", "alarm clock ringing morning", "waking up sunrise"],
    "dream": ["looking at night stars sky", "contemplative person sunset", "visionary horizon view"],
    "discipline": ["person focused studying desk", "early morning alarm clock", "writing journal concentration"],
    "money": ["cash dollars counting hands", "credit card payment luxury", "gold bars vault investment"],
    "wealth": ["luxury mansion penthouse", "private luxury lifestyle yacht", "successful investor office"],
    "success": ["businessman celebrating victory summit", "climbing mountain peak success", "confident executive walking"],
    "work": ["modern office team meeting", "laptop typing coder late night", "industrial worker hands factory"],
    "walk": ["person walking through city street", "crowd commuting subway station", "walking along empty foggy road"],
    "city": ["new york city aerial timelapse", "busy urban pedestrian crosswalk", "neon city streets night"],
    "rain": ["rain drops on window glass moody", "walking in rain umbrella lonely", "wet asphalt city rain reflections"],
    "silence": ["calm peaceful lake reflection", "quiet empty room sunset light", "serene snowy forest silence"],
    "starving": ["longing hungry expression portrait", "pensive man staring into space", "reaching hand towards light"],
    "waiting": ["person waiting train platform", "clock ticking time passing timelapse", "sitting alone cafe window"],
    "fight": ["medieval sword battle cinematic", "epic war soldiers charging", "ancient warriors clash"],
    "fighting": ["ancient warriors battle clash", "soldiers charging battlefield", "medieval combat swords"],
    "morning": ["golden sunrise horizon dawn", "drinking coffee morning window", "morning sun rays trees"],
    "future": ["futuristic technology glowing interface", "modern architecture minimalist", "virtual reality headset person"],
    "missile": ["ballistic missile launch", "rocket launch night", "missile explosion"],
    "ballistic": ["ballistic missile launch", "missile flight trajectory", "military rocket"],
    "blastoc": ["ballistic missile launch", "military rocket explosion"],
    "misile": ["ballistic missile launch", "missile rocket launch"],
    "war": ["military battlefield soldiers", "war explosion smoke", "military combat tank"],
    "army": ["military soldiers marching", "armed forces tactical", "military base"],
    "military": ["military base operations", "armed forces soldiers", "military vehicles convoy"],
    "attack": ["military strike explosion", "airstrike explosion", "tactical combat"],
    "strike": ["airstrike explosion", "missile impact explosion", "military strike"],
    "explosion": ["huge fiery explosion", "battlefield explosion", "detonation smoke fire"],
    "dhamaka": ["huge fiery explosion", "military explosion", "blast detonation"],
    "bomb": ["bomb detonation explosion", "fighter jet bombing", "tactical bomb drop"],
    "drone": ["military drone flying", "uav surveillance drone", "aerial drone strike"],
    "rocket": ["rocket launch smoke", "rocket propulsion night", "military rocket"],
    "tank": ["military tank moving", "armored vehicle battlefield", "tank firing cannon"],
    "soldier": ["soldiers in uniform patrol", "armed tactical soldier", "combat troops marching"],
    "fauj": ["military soldiers marching", "armed forces patrol", "military infantry"],
    "jang": ["war explosion battlefield", "military combat", "war smoke fire"],
    "weapon": ["military weapon arsenal", "tactical firearms shooting", "defense weapons system"],
    "iran": ["middle east desert landscape", "tehran city skyline", "military base middle east"],
    "israel": ["tel aviv city aerial", "middle east desert landscape", "military defense iron dome"],
    "defense": ["air defense radar", "military defense system", "anti missile system"],
    "radar": ["military radar antenna spinning", "air defense radar screen", "surveillance radar"],
    "fighter": ["fighter jet supersonic", "military aircraft flight", "air force jet takeoff"],
    "jet": ["fighter jet in clouds", "supersonic combat jet", "military aviation"],
    "aircraft": ["military aircraft carrier", "fighter jet takeoff", "warplane flying sky"],
    "soldiers": ["soldiers in uniform patrol", "armed tactical soldiers", "combat troops marching"],
    "tanks": ["military tanks moving", "armored vehicles battlefield", "tanks firing cannons"],
    "missiles": ["ballistic missile launch", "military rocket trajectory", "air defense missiles"],
    "weapons": ["military weapons arsenal", "tactical firearms shooting", "defense weapon systems"],
    "bombs": ["bomb detonation explosion", "fighter jet bombing", "tactical bombs explosion"],
    "explosions": ["huge fiery explosions", "battlefield explosions smoke", "artillery detonation"],
    "warriors": ["combat soldiers armed troops", "tactical warriors battlefield", "military infantry"],
    "battles": ["military battlefield soldiers fighting", "war combat armored forces", "infantry battle smoke"],
    "attacks": ["military airstrikes explosions", "tactical combat offensive", "battlefield attacks"],
    "navy": ["navy warship ocean sailing", "military aircraft carrier", "naval fleet battleship"],
    "warship": ["navy warship ocean sailing", "military naval destroyer", "naval battleship fleet"],
    "submarine": ["navy submarine underwater", "military submarine ocean", "naval submarine patrol"],
    "submarines": ["military submarine ocean", "navy submarine underwater", "naval submarine patrol"],
    "airforce": ["fighter jet supersonic takeoff", "military air force warplane", "fighter jets in formation"],
    "artillery": ["military artillery firing cannon", "howitzer cannon smoke", "tactical artillery battery"],
    "sniper": ["tactical military sniper", "special forces sniper rifle", "camouflaged soldier aiming"],
    "convoy": ["military vehicle convoy desert", "armored troop convoy", "military truck patrol"],
    "infantry": ["military infantry soldiers patrol", "armed troops marching", "tactical infantry combat"],
    "combat": ["military battlefield combat", "tactical armed combat troops", "infantry soldiers fighting"],
    "battlefield": ["war battlefield smoke explosion", "military combat zone", "battlefield soldiers"],
    "frontline": ["soldiers on front line", "military trench combat", "frontline battlefield armed"],
    # Space & Astronomy
    "space": ["deep space galaxy stars", "astronaut spacewalk earth", "space shuttle launch"],
    "planet": ["planet earth orbit", "solar system planets", "jupiter saturn rings"],
    "galaxy": ["milky way galaxy night", "spiral galaxy hubble", "deep space nebula stars"],
    "orbit": ["satellite orbiting earth", "international space station", "spacecraft orbit"],
    "astronaut": ["astronaut spacewalk helmet", "astronaut moon surface", "astronaut floating station"],
    "star": ["stars night sky timelapse", "stellar nebula cosmos", "shooting star meteor"],
    "solar": ["solar system animation", "solar flare sun surface", "solar eclipse dramatic"],
    "moon": ["full moon night sky", "lunar surface craters", "moon landing apollo"],
    "mars": ["mars red planet surface", "mars rover exploration", "mars colony concept"],
    "nasa": ["nasa rocket launch", "nasa space mission", "nasa control room"],
    "satellite": ["satellite orbiting earth", "communication satellite space", "satellite dish antenna"],
    "telescope": ["telescope observatory night", "hubble telescope deep space", "telescope stargazing"],
    "cosmos": ["cosmos universe stars", "cosmic nebula colorful", "deep space exploration"],
    "universe": ["universe expanding cosmos", "deep space stars galaxy", "cosmic nebula"],
    "nebula": ["colorful nebula hubble", "space nebula gas clouds", "stellar nursery nebula"],
    "blackhole": ["black hole visualization", "event horizon space", "black hole accretion"],
    "comet": ["comet tail night sky", "comet approaching earth", "asteroid comet space"],
    "asteroid": ["asteroid belt space", "asteroid approaching earth", "meteor asteroid impact"],
    "gravity": ["zero gravity floating", "astronaut weightless space", "gravity physics"],
    "launch": ["rocket launch countdown", "space shuttle launch pad", "spacecraft launch flames"],
    # Science & Technology
    "science": ["scientific laboratory experiment", "molecular structure 3d", "scientist research lab"],
    "technology": ["futuristic technology interface", "circuit board electronics", "innovation technology"],
    "computer": ["computer code programming", "server room data center", "typing keyboard screen"],
    "internet": ["global network connections", "fiber optic data", "digital world connected"],
    "robot": ["humanoid robot advanced", "robotic arm factory", "artificial intelligence robot"],
    "brain": ["human brain neural network", "brain scan medical", "neurons firing brain"],
    "energy": ["renewable energy windmill", "solar panels field", "nuclear power plant"],
    "nuclear": ["nuclear power plant", "atomic energy reactor", "nuclear physics"],
    "electric": ["electric power grid", "lightning bolt storm", "electric car charging"],
    # Ocean & Marine
    "ocean": ["deep ocean underwater", "ocean waves aerial drone", "underwater coral reef"],
    "sea": ["calm sea horizon sunset", "stormy sea waves crashing", "deep sea creatures"],
    "underwater": ["underwater coral reef fish", "deep sea diving", "underwater ocean life"],
    "whale": ["whale underwater ocean", "humpback whale breach", "blue whale deep sea"],
    "fish": ["tropical fish coral reef", "school of fish ocean", "deep sea fish"],
    "swim": ["person swimming pool", "olympic swimming race", "swimming underwater blue"],
    # Education & Knowledge
    "learn": ["student studying library", "classroom education learning", "books reading knowledge"],
    "school": ["school classroom students", "university campus aerial", "graduation ceremony"],
    "book": ["open book reading light", "library books shelves", "ancient manuscript book"],
    "study": ["student studying desk night", "focused studying library", "research study papers"],
    "history": ["ancient historical ruins", "historical documentary footage", "old civilization artifacts"],
    "ancient": ["ancient temple ruins", "ancient civilization archaeology", "historical ancient statue"],
    # Economy & Politics
    "economy": ["stock market trading floor", "economic growth chart", "global economy finance"],
    "politics": ["government parliament building", "political speech podium", "voting election democracy"],
    "president": ["presidential speech podium", "white house building", "political leader address"],
    "election": ["voting ballot box election", "election campaign rally", "democratic voting process"],
    "government": ["government capitol building", "parliament session debate", "official government meeting"],
    # Health & Medical
    "health": ["healthy lifestyle exercise", "medical hospital care", "wellness meditation yoga"],
    "doctor": ["doctor medical examination", "surgeon operating room", "medical professional stethoscope"],
    "virus": ["virus microscope 3d", "pandemic medical response", "viral infection cells"],
    "medicine": ["pharmaceutical medicine pills", "medical research laboratory", "hospital medicine care"],
    "surgery": ["surgeon operating theater", "surgical operation precision", "hospital surgical equipment"],
    "dna": ["dna double helix 3d", "genetic code molecular biology", "dna strand glowing lab"],
    "cell": ["microscopic living cells", "cell division biology microscope", "human cells medical laboratory"],
    "cells": ["microscopic living cells", "cellular biology research", "microscope blood cells"],
    "bacteria": ["bacteria cells microscope", "microbiology bacterial culture", "microscopic organisms lab"],
    "heart": ["human heart 3d beating", "cardiology medical monitor", "healthy heart heartbeat ecg"],
    "blood": ["blood cells flowing vessel", "microscope red blood cells", "medical blood test laboratory"],
    "laboratory": ["scientific research laboratory", "scientist looking microscope", "chemistry test tubes glowing"],
    "microscope": ["scientist looking microscope lab", "microscopic specimen view", "laboratory microscope research"],
    "dimagh": ["human brain neural network", "brain scan medical", "neurons firing brain"],
    "sehat": ["healthy lifestyle exercise", "medical hospital care", "wellness meditation yoga"],
    "ilaj": ["doctor medical examination", "pharmaceutical medicine pills", "hospital medical treatment"],
    "beemari": ["virus microscope 3d", "patient hospital bed care", "medical examination doctor"],
    "jism": ["human anatomy 3d model", "athletic human body motion", "human muscles movement"],
    "khoon": ["blood cells flowing vessel", "microscope red blood cells", "medical laboratory testing"],

    # Nature & Weather & Disasters
    "mountain": ["mountain peak aerial snow", "hiking mountain summit", "majestic mountain landscape"],
    "forest": ["dense forest aerial misty", "walking through forest trail", "sunlight through forest trees"],
    "desert": ["vast desert sand dunes", "desert sunset dramatic sky", "sahara desert landscape"],
    "volcano": ["active volcano eruption lava", "volcanic eruption smoke", "volcano lava flowing"],
    "earthquake": ["earthquake destruction buildings", "seismic earthquake damage", "earthquake rescue response"],
    "storm": ["thunderstorm lightning dramatic", "hurricane storm satellite", "tornado storm destruction"],
    "fire": ["wildfire forest burning", "fire flames dramatic", "firefighter emergency response"],
    "ice": ["arctic ice glacier frozen", "ice melting climate change", "frozen landscape winter"],
    "tsunami": ["huge ocean tsunami wave", "ocean tidal wave destruction", "massive sea wave storm"],
    "tornado": ["tornado twister approaching field", "violent tornado storm destruction", "supercell storm funnel cloud"],
    "hurricane": ["hurricane storm satellite view", "extreme wind hurricane destruction", "tropical storm crashing waves"],
    "lightning": ["dramatic lightning strike night", "thunderstorm lightning flashing", "lightning bolt dark clouds"],
    "flood": ["flood rising water city", "aerial river flood destruction", "torrential rain flood rescue"],
    "avalanche": ["snow avalanche mountain slope", "massive snow avalanche sliding", "winter mountain snow slide"],
    "blizzard": ["heavy snow blizzard walking", "snowstorm winter wind blizzard", "freezing snow storm landscape"],
    "zalzala": ["earthquake destruction buildings", "seismic earthquake damage", "ruined buildings rubble"],
    "toofan": ["thunderstorm lightning dramatic", "hurricane storm satellite", "tornado storm destruction"],
    "bijli": ["dramatic lightning strike night", "thunderstorm lightning flashing", "lightning bolt dark clouds"],
    "sailab": ["flood rising water city", "torrential river flood rescue", "aerial flood disaster water"],
    "tabahi": ["massive fiery explosion smoke", "earthquake destruction buildings", "ruined disaster landscape"],

    # Wildlife, Predators & Marine Life (1000+ Topics: Animals, Oceans, Safari)
    "tiger": ["bengal tiger walking jungle", "tiger stalking prey forest", "tiger roaring intense eyes"],
    "tigers": ["bengal tiger walking jungle", "tiger family snow siberia", "predator tiger prowling"],
    "lion": ["male lion roaring savannah", "lion pride golden sunrise", "lion hunting prey african plains"],
    "lions": ["lion pride resting savannah", "male lion majestic mane", "lions hunting zebra plains"],
    "cheetah": ["cheetah sprinting fast savannah", "cheetah running full speed", "cheetah stalking gazelle"],
    "leopard": ["leopard climbing tree branch", "snow leopard rocky mountain", "leopard stalking prey night"],
    "jaguar": ["jaguar swimming river amazon", "jaguar prowling dense rainforest", "predator jaguar stealth"],
    "panther": ["black panther glowing eyes", "black panther stalking forest", "black leopard prowling"],
    "wolf": ["wolf pack running snow", "lone wolf howling moon", "wild wolves hunting wilderness"],
    "wolves": ["wolf pack winter forest snow", "alpha wolf staring camera", "wolves running wilderness"],
    "bear": ["grizzly bear catching salmon", "polar bear walking arctic ice", "brown bear wilderness forest"],
    "bears": ["grizzly bear fishing river", "polar bear cubs snow", "brown bear wandering forest"],
    "elephant": ["elephant herd walking savannah", "african elephant waterhole sunset", "majestic elephant dust spray"],
    "elephants": ["elephant herd african plains", "wild elephants river crossing", "mother elephant baby calf"],
    "rhino": ["white rhinoceros savannah grass", "armored rhino charging dust", "wild rhino walking wilderness"],
    "giraffe": ["giraffes walking savannah sunset", "giraffe eating acacia tree", "tall giraffe aerial plains"],
    "zebra": ["zebra herd running plains", "zebras crossing crocodile river", "zebra stripes running wild"],
    "eagle": ["bald eagle soaring mountain", "golden eagle hunting aerial", "eagle diving catching fish talons"],
    "eagles": ["bald eagle flying sky", "golden eagle cliff nest", "eagle soaring thermal currents"],
    "hawk": ["hawk perched tree branch", "hawk diving hunting speed", "wild hawk flying dramatic sky"],
    "falcon": ["peregrine falcon diving speed", "falcon flying desert dunes", "hunting falcon striking midair"],
    "owl": ["snowy owl silent flight", "great horned owl night eyes", "barn owl flying barn dark"],
    "vulture": ["vulture circling desert sky", "vultures perched dead tree", "wild vulture scavengers"],
    "shark": ["great white shark underwater", "hammerhead shark swimming reef", "predator shark ocean depths"],
    "sharks": ["great white shark hunting", "reef sharks swimming crystal water", "underwater shark encounter"],
    "whale": ["humpback whale ocean breach", "blue whale swimming deep ocean", "killer whale orca pod ocean"],
    "whales": ["humpback whale mother calf", "pod of whales migrating sea", "whale tail fluke diving water"],
    "orca": ["killer whale orca breaching", "orca pod hunting ocean", "killer whale swimming arctic"],
    "dolphin": ["dolphins jumping ocean waves", "pod of dolphins swimming clear water", "playful dolphin underwater"],
    "dolphins": ["dolphins leaping ocean sunset", "underwater dolphins swimming pods", "wild dolphins riding waves"],
    "octopus": ["giant octopus underwater coral", "octopus changing color camouflage", "deep sea octopus swimming"],
    "crocodile": ["crocodile waiting river edge", "massive saltwater crocodile water", "crocodile ambush water splash"],
    "alligator": ["alligator swimming swamp mist", "alligator jaw snapping water", "florida everglades alligator"],
    "snake": ["venomous snake strike slow motion", "king cobra raising hood", "green viper snake tree branch"],
    "snakes": ["coiled python snake scales", "rattlesnake striking desert sand", "exotic snake slithering jungle"],
    "cobra": ["king cobra raising hood threat", "hooded cobra snake eyes", "black cobra striking defensive"],
    "python": ["huge burmese python slithering", "python wrapped tree branch", "giant snake rainforest jungle"],
    "gorilla": ["silverback gorilla mountain mist", "gorilla family rainforest jungle", "powerful gorilla beating chest"],
    "monkey": ["chimpanzee tool use forest", "monkeys swinging jungle canopy", "wild baboon troop savannah"],
    "horse": ["wild horses running galloping", "black stallion galloping sunset", "white horse running wild meadow"],
    "horses": ["herd of wild horses galloping", "running horses kicking dust", "mustang horses running plain"],
    "deer": ["majestic stag deer forest mist", "deer running meadow morning", "elk with large antlers forest"],
    "fox": ["red fox jumping snow hunt", "arctic fox running white snow", "wild fox wandering forest trail"],
    "hyena": ["spotted hyena savannah night", "hyena pack wandering plains", "wild hyena scavenging sunset"],
    "penguin": ["emperor penguins arctic ice", "penguins diving ocean water", "colony of penguins snow antarctica"],
    "penguins": ["emperor penguins walking ice", "penguins swimming fast underwater", "penguin colony antarctica"],
    "seal": ["leopard seal underwater swimming", "fur seals resting ocean rocks", "baby harp seal arctic ice"],
    "jellyfish": ["bioluminescent jellyfish glowing", "deep sea jellyfish floating dark", "translucent jellyfish pulsing"],
    "coral": ["vibrant coral reef underwater 4k", "tropical fish swimming coral", "ocean coral reef biodiversity"],
    "safari": ["african safari 4k wildlife", "safari jeep savannah sunset", "wild animals watering hole safari"],
    "predator": ["apex predator stalking prey", "lion hunting gazelle savannah", "wild predator attacking ambush"],
    "prey": ["gazelle escaping predator run", "herd of prey running plains", "wild animal alert listening danger"],
    "hunt": ["lion stalking hunting prey", "cheetah chasing fast sprint", "predator animal hunting savannah"],
    "hunting": ["wild predator hunting prey", "eagle diving hunting fish", "lion pride hunting dusk"],
    "sher": ["male lion roaring savannah", "bengal tiger walking jungle", "lion pride golden sunrise"],
    "cheeta": ["cheetah sprinting fast savannah", "cheetah running full speed", "predator cheetah hunting"],
    "bagh": ["bengal tiger walking jungle", "tiger stalking prey forest", "wild tiger river jungle"],
    "janwar": ["wild animals african savannah", "wildlife creatures forest 4k", "animals drinking watering hole"],
    "bheriya": ["wolf pack running snow", "lone wolf howling moon", "wild wolves hunting wilderness"],
    "hathi": ["elephant herd walking savannah", "african elephant waterhole sunset", "majestic elephant dust spray"],
    "saanp": ["venomous snake strike slow motion", "king cobra raising hood", "green viper snake tree branch"],
    "magarmach": ["crocodile waiting river edge", "massive saltwater crocodile water", "crocodile ambush water splash"],
    "chil": ["eagle soaring mountain thermals", "golden eagle hunting aerial", "hawk diving hunting speed"],
    "baaz": ["falcon diving speed aerial", "peregrine falcon hunting", "hawk diving hunting speed"],
    "shikar": ["lion hunting prey savannah", "cheetah sprinting fast prey", "eagle diving catching fish talons"],
    "parinda": ["flock of birds flying sunset", "exotic tropical bird rainforest", "eagle soaring sky clouds"],
    "machli": ["tropical fish coral reef 4k", "school of fish ocean blue", "deep sea colorful fish reef"],
    "ghoda": ["wild horses running galloping", "black stallion galloping sunset", "running horse meadow"],
    "hiran": ["majestic stag deer forest mist", "deer running meadow morning", "wild gazelle running savannah"],

    # History, Empires & Ancient Civilizations (1000+ Topics: Rome, Egypt, Vikings, Ottomans)
    "pyramid": ["pyramids of giza golden sunset", "ancient egyptian pyramid aerial", "cairo pyramids desert landscape"],
    "pyramids": ["giza pyramids golden hour aerial", "ancient pyramids desert sunset", "great pyramid archaeological ruins"],
    "pharaoh": ["ancient egyptian pharaoh tomb", "tutankhamun golden burial mask", "egyptian temple wall hieroglyphics"],
    "egypt": ["ancient egypt nile river cruise", "karnak temple luxor egypt", "ancient egyptian ruins monument"],
    "sphinx": ["great sphinx of giza aerial", "egyptian sphinx desert sunset", "ancient sphinx monument sand"],
    "mummy": ["egyptian mummy tomb archaeology", "ancient sarcophagus golden tomb", "museum mummy artifact relics"],
    "tomb": ["ancient stone tomb torch light", "royal underground tomb ruins", "historical burial tomb excavation"],
    "rome": ["ancient roman colosseum aerial", "roman forum historical ruins", "rome historical architecture sunset"],
    "roman": ["roman legionary soldiers shield", "ancient roman colosseum ruins", "roman empire classical statue"],
    "gladiator": ["roman gladiator colosseum arena", "ancient gladiator combat sword", "gladiator arena crowd cheering"],
    "colosseum": ["colosseum rome aerial 4k", "ancient roman colosseum interior", "colosseum sunset dramatic sky"],
    "caesar": ["julius caesar marble statue", "ancient roman senate debate", "roman emperor toga marble statue"],
    "sparta": ["spartan warriors shield spear", "ancient greek hoplite soldiers", "spartan warrior helmet bronze"],
    "greece": ["parthenon acropolis athens sunset", "ancient greek temple ruins", "classical greek marble statues"],
    "medieval": ["medieval stone castle fortress", "medieval knights armor swords", "medieval village market cobblestone"],
    "knight": ["medieval knight armor broadsword", "mounted knight horse lance", "armored knight walking fortress"],
    "knights": ["medieval knights charging battle", "knights in plate armor duel", "knights templar procession flags"],
    "sword": ["medieval steel sword gleaming", "blacksmith forging steel sword", "ancient sword stuck in stone"],
    "shield": ["viking shield wall formation", "roman legionary rectangular shield", "medieval knight wooden shield"],
    "armor": ["steel plate armor knight gleaming", "ancient roman lorica segmentata", "medieval armor museum display"],
    "castle": ["medieval stone castle cliff aerial", "fairy tale stone castle fortress", "ancient castle ruins foggy mist"],
    "castles": ["aerial medieval castles europe", "stone fortress castle battlements", "ancient gothic castle landscape"],
    "fortress": ["ancient mountain stone fortress", "medieval fortress walls defense", "citadel fortress watchtowers aerial"],
    "catapult": ["medieval siege catapult firing", "siege weapons fortress attack", "trebuchet firing fiery rock"],
    "archery": ["medieval archer drawing longbow", "arrow flying hitting bullseye", "ancient archers firing volleys"],
    "viking": ["viking longship sailing fjord", "viking warrior axe battle cry", "viking village wooden longhouses"],
    "vikings": ["viking longships sailing ocean", "viking warriors charging shore", "nordic viking shield wall fight"],
    "ottoman": ["ottoman empire palace architecture", "topkapi palace istanbul aerial", "historical ottoman janissary soldiers"],
    "sultan": ["ottoman sultan throne room", "grand royal palace throne", "historical oriental emperor palace"],
    "emperor": ["imperial emperor throne room", "ancient emperor royal court", "roman emperor marble bust"],
    "dynasty": ["ancient forbidden city china", "chinese imperial palace aerial", "ancient dynasty terracotta warriors"],
    "samurai": ["japanese samurai katana sword", "samurai warrior traditional armor", "samurai duel cherry blossoms"],
    "ninja": ["ninja shadow assassin night", "black ninja rooftop stealth", "traditional shinobi martial art"],
    "mongol": ["mongol horse archers steppe", "genghis khan cavalry galloping", "mongolian nomadic horsemen plains"],
    "ruins": ["ancient temple ruins overgrown", "historical stone ruins drone", "civilization ruins archaeological"],
    "archaeology": ["archaeologist brushing ancient artifact", "archaeological excavation site dig", "uncovering ancient relics dirt"],
    "artifact": ["ancient gold artifact museum", "historical relic archaeological find", "ancient carved stone tablet"],
    "tareekh": ["ancient historical ruins drone", "old civilization artifacts museum", "historical documentary footage"],
    "qadeem": ["ancient temple ruins stone", "old civilization archaeology", "historical ancient monument ruins"],
    "badshah": ["imperial emperor royal throne", "ancient king royal palace court", "historical crown royal majesty"],
    "saltanat": ["ottoman empire grand palace", "ancient imperial kingdom citadel", "majestic stone castle fortress"],
    "ahraam": ["pyramids of giza golden sunset", "ancient egyptian pyramid aerial", "cairo pyramids desert landscape"],
    "mehal": ["grand royal palace interior", "majestic palace architecture aerial", "ancient imperial palace gardens"],
    "qila": ["ancient mountain stone fortress", "medieval stone castle cliff aerial", "fortress walls towers defense"],
    "talwar": ["medieval steel sword gleaming", "blacksmith forging steel sword", "ancient sword stuck in stone"],
    "sipahi": ["soldiers in uniform marching", "ancient warriors shield formation", "armed guards palace gates"],
    "khandar": ["ancient temple ruins overgrown", "historical stone ruins drone", "abandoned ancient stone ruins"],

    # Crime, Mystery, True Crime, Law & Justice (1000+ Topics)
    "crime": ["police crime scene yellow tape", "detective flashlight dark alley", "crime investigation evidence board"],
    "criminal": ["shadowy criminal dark alley", "handcuffed suspect police car", "prisoner behind jail bars"],
    "detective": ["detective silhouette trench coat", "detective examining crime scene", "vintage detective typing report"],
    "investigation": ["detective evidence pinboard photos", "forensic scientist laboratory evidence", "magnifying glass examining clue"],
    "police": ["police car siren flashing night", "police officers tactical uniform", "police emergency lights reflection"],
    "siren": ["police siren red blue flashing", "emergency vehicle siren night", "ambulance siren flashing street"],
    "handcuffs": ["police arresting suspect handcuffs", "metallic handcuffs clicked shut", "suspect led away handcuffs"],
    "arrest": ["police arresting suspect night", "police officers raiding building", "police tactical arrest team"],
    "prison": ["prison cell iron bars corridor", "high security prison guard tower", "inmates walking prison yard"],
    "prisoner": ["inmate walking prison hallway", "prisoner hands holding cell bars", "orange jumpsuit inmate yard"],
    "jail": ["jail cell door closing heavy", "iron jail bars dark prison", "prison cell corridor lights"],
    "courtroom": ["judge gavel hitting wooden block", "lawyer presenting courtroom trial", "empty courtroom wooden benches"],
    "judge": ["judge banging wooden gavel", "supreme court judge robes", "judge listening courtroom trial"],
    "gavel": ["wooden judge gavel striking desk", "auctioneer gavel slamming wood", "legal gavel closeup sound"],
    "jury": ["jury members listening courtroom", "jury deliberating decision room", "trial jury verdict delivered"],
    "lawyer": ["lawyer examining legal documents", "attorney arguing case court", "confident lawyer walking courthouse"],
    "interrogation": ["detective interrogation dark room", "suspect sweating interrogation light", "two detectives questioning suspect"],
    "fingerprint": ["forensic fingerprint powder brush", "biometric fingerprint scanner screen", "fingerprint analysis magnifying glass"],
    "forensic": ["forensic investigator white suit", "forensic science laboratory dna", "crime scene investigation markers"],
    "robbery": ["masked bank robbery vault guns", "burglar flashlight break in", "security camera robbery footage"],
    "heist": ["bank vault door opening wheels", "vault room stacks of cash", "laser alarm security grid heist"],
    "vault": ["massive steel bank vault door", "underground bank vault safe boxes", "golden vault bars cash stacks"],
    "surveillance": ["security cctv camera rotating wall", "security room multiple screens", "cctv surveillance footage monitor"],
    "suspect": ["suspect lineup police wall height", "shadowy figure running alley", "police interrogation room suspect"],
    "mafia": ["gangster vintage pinstripe suit", "mafia meeting shadowy room cigars", "classic mobster car driving night"],
    "gangster": ["mobster holding retro tommy gun", "gangster smoke cigar luxury car", "shadowy underworld boss meeting"],
    "murder": ["detective inspecting blood spatter", "crime scene tape windy night", "noir detective crime investigation"],
    "mystery": ["foggy night street lamp mystery", "silhouette shadowy figure fog", "magnifying glass old map riddle"],
    "jurm": ["police crime scene yellow tape", "detective flashlight dark alley", "handcuffed suspect police car"],
    "mujrim": ["shadowy criminal dark alley", "handcuffed suspect police car", "prisoner behind jail bars"],
    "qaid": ["prison cell iron bars corridor", "inmates walking prison yard", "iron jail bars dark prison"],
    "adalat": ["judge gavel hitting wooden block", "courtroom trial lawyer presentation", "supreme court marble pillars"],
    "qatil": ["detective inspecting crime scene", "shadowy figure running dark alley", "police arresting suspect night"],
    "qatal": ["crime scene tape windy night", "police car siren flashing rain", "forensic evidence marker floor"],
    "chor": ["burglar flashlight dark house", "masked robber breaking lock", "security camera intruder footage"],
    "daku": ["masked bank robbery vault guns", "armed bandits desert horseback", "criminal getaway car speed"],
    "tehqeeqat": ["detective evidence pinboard photos", "forensic scientist laboratory evidence", "magnifying glass examining clue"],

    # Horror, Paranormal, Creepy & Supernatural (1000+ Topics)
    "horror": ["creepy abandoned house full moon", "eerie dark forest mist foggy", "shadowy figure lurking darkness"],
    "scary": ["flickering light dark hallway", "eerie silhouette standing window", "mysterious glowing eyes dark"],
    "ghost": ["ethereal ghost apparition hallway", "transparent phantom floating dark", "creepy white figure dark woods"],
    "ghosts": ["misty cemetery ghosts silhouettes", "paranormal apparition old house", "spooky shadows moving wall"],
    "haunted": ["creepy abandoned Victorian mansion", "haunted house thunderstorm night", "creaking door opening dark room"],
    "creepy": ["creepy porcelain doll staring", "shadowy hands reaching darkness", "flickering fluorescent corridor eerie"],
    "eerie": ["eerie foggy swamp dead trees", "mist rising desolate landscape", "spooky full moon glowing clouds"],
    "graveyard": ["foggy graveyard tombstones night", "ancient cemetery crosses mist", "gargoyle statue misty cemetery"],
    "cemetery": ["old gothic cemetery gravestones", "full moon shining cemetery", "mist rolling over graveyard stones"],
    "shadows": ["creepy dark shadows on wall", "mysterious long silhouette floor", "dark shadowy figure approaching"],
    "witch": ["witch stirring smoking cauldron", "hooded witch chanting dark woods", "witchcraft ritual candle circle"],
    "vampire": ["vampire rising ancient coffin", "gothic vampire castle night", "fanged shadow red eyes darkness"],
    "monster": ["giant monster shadow fog", "creature lurking dark swamp", "terrifying beast glowing eyes night"],
    "nightmare": ["person waking up gasping bed", "dark surreal nightmare corridor", "shadowy hands reaching bedside"],
    "bhoot": ["creepy abandoned house full moon", "eerie dark forest mist foggy", "ethereal ghost apparition hallway"],
    "chudail": ["hooded witch dark woods night", "creepy silhouette flying moon", "eerie female figure dark forest"],
    "darawna": ["flickering light dark hallway", "creepy porcelain doll staring", "mysterious shadowy figure darkness"],
    "khauf": ["terrified person wide eyes fear", "running through dark woods fear", "heart beating fast fear shadow"],
    "qabristan": ["foggy graveyard tombstones night", "ancient cemetery crosses mist", "mist rolling over graveyard stones"],
    "saya": ["creepy dark shadows on wall", "mysterious long silhouette floor", "shadowy figure lurking darkness"],
    "khofnak": ["creepy abandoned Victorian mansion", "giant monster shadow fog", "eerie foggy swamp dead trees"],

    # Automotive, Supercars, Racing & Aviation (1000+ Topics)
    "car": ["luxury sports car driving highway", "modern sleek electric vehicle road", "sports car accelerating sunset"],
    "cars": ["supercars driving mountain road", "traffic city highway night lights", "expensive exotic cars parked showroom"],
    "supercar": ["matte black supercar drifting track", "lamborghini accelerating fast track", "ferrari roaring engine speed"],
    "supercars": ["lineup exotic supercars revving", "supercars racing track aerial", "luxury sports cars showroom floor"],
    "racing": ["formula 1 race cars speed blur", "rally car drifting dirt road", "sports car racetrack corner drift"],
    "drift": ["supercar drifting burning rubber smoke", "drift car sliding corner track", "night street drift neon lights"],
    "engine": ["car engine pistons firing combustion", "twin turbo supercar engine revving", "mechanic working high tech engine"],
    "motorcycle": ["superbike leaning sharp turn track", "biker riding highway sunset", "custom chopper motorcycle road"],
    "airplane": ["commercial airliner takeoff clouds", "airplane wing sunset sky aerial", "passenger airplane landing runway"],
    "helicopter": ["rescue helicopter flying mountains", "military attack helicopter flight", "black hawk helicopter landing dust"],
    "pilot": ["airplane pilot cockpit controls flight", "fighter jet pilot helmet visor", "pilot hands adjusting throttle flight"],
    "airport": ["busy international airport runway", "airplane parked boarding gate", "air traffic control tower sunset"],
    "train": ["high speed bullet train tracks", "scenic passenger train mountain bridge", "subway train arriving station"],
    "yacht": ["luxury mega yacht cruising turquoise ocean", "private yacht deck champagne sunset", "superyacht aerial blue water"],
    "gari": ["luxury sports car driving highway", "matte black supercar drifting track", "sports car accelerating sunset"],
    "jahaz": ["commercial airliner takeoff clouds", "navy warship ocean sailing", "military aircraft carrier flight"],
    "raftar": ["formula 1 race cars speed blur", "supercar accelerating highway speed", "speedometer needle accelerating fast"],

    # Technology, AI, Cyber, Robotics & Metaverse (1000+ Topics)
    "ai": ["artificial intelligence glowing brain", "neural network glowing connections", "futuristic ai interface holograms"],
    "robot": ["humanoid robot walking forward", "robotic mechanical arm assembly factory", "advanced android robot face glowing"],
    "robots": ["humanoid robots working together", "robotic automated factory floor", "swarm of robots automated warehouse"],
    "cyber": ["cyberpunk city neon rain night", "cyber security padlock digital matrix", "binary code glowing green screen"],
    "cybersecurity": ["cyber security defense shield glowing", "hacker terminal code security breach", "data encryption locks server"],
    "hacker": ["hacker typing hoodie dark room", "multiple monitors green code scrolling", "cyber attack warning screen red"],
    "hacking": ["cyber attack terminal code exploit", "unauthorized access warning blinking", "code breaking firewall screen"],
    "code": ["programmer typing code screen", "clean code scrolling dark theme", "software development web coding"],
    "coding": ["developer coding dual monitors late", "hands typing mechanical keyboard code", "software engineer writing code"],
    "server": ["server room blue led data center", "racks of glowing computer servers", "cloud computing data server facility"],
    "servers": ["endless corridor server racks glowing", "data center cooling system fans", "enterprise server infrastructure"],
    "cpu": ["microprocessor chip glowing circuit", "computer cpu processor wafer macro", "motherboard microchips golden tracks"],
    "quantum": ["quantum computer chandelier golden glowing", "quantum physics qubits visualization", "supercomputer laboratory glowing blue"],
    "hologram": ["futuristic 3d hologram rotating", "hands interacting holographic interface", "holographic world globe spinning"],
    "metaverse": ["person wearing vr headset virtual world", "digital avatar virtual reality landscape", "cyberpunk neon virtual reality world"],

    # Finance, Wealth, Crypto, Business & Luxury (1000+ Topics)
    "crypto": ["bitcoin gold coin glowing digital", "cryptocurrency trading chart screens", "ethereum blockchain digital network"],
    "bitcoin": ["golden bitcoin coin rotating macro", "bitcoin chart green candlestick surge", "crypto mining computer rigs glowing"],
    "trading": ["stock trader multi monitor charts", "forex trading candlesticks moving green", "day trader analyzing financial market"],
    "trader": ["wall street stock trader shouting", "focused trader looking screen charts", "businessman financial trading desk"],
    "dollar": ["stack of 100 dollar bills counting", "cash money falling slow motion", "crisp us dollars fan out hands"],
    "dollars": ["hundred dollar bills stacks cash", "suitcase full of money dollars", "counting us dollar notes machine"],
    "gold": ["shining gold bars stacked vault", "liquid molten gold pouring ingot", "solid gold bullion glowing light"],
    "paisa": ["cash dollars counting hands", "stack of 100 dollar bills counting", "gold bars vault investment"],
    "paise": ["cash dollars counting hands", "stack of 100 dollar bills counting", "counting money cash table"],
    "daulat": ["luxury mansion penthouse sunset", "private luxury lifestyle yacht", "gold bars stacked vault"],
    "ameer": ["billionaire luxury lifestyle private jet", "successful executive penthouse view", "supercar driving luxury villa"],
    "khazana": ["ancient treasure chest golden coins", "bank vault stacks of gold bars", "glowing gold treasure coins"],
    "tijarat": ["stock market trading floor busy", "modern business port cargo containers", "global commerce shipping logistics"],
    "karobar": ["modern glass office boardroom meeting", "successful startup founders presentation", "handshake business deal office"],

    # Sports, Athletics & Fitness (1000+ Topics)
    "football": ["soccer player kicking ball goal stadium", "soccer ball net goal celebration", "crowded football stadium lights night"],
    "soccer": ["professional soccer match stadium", "striker scoring bicycle kick goal", "football fans cheering stadium smoke"],
    "cricket": ["cricket batsman hitting boundary shot", "fast bowler bowling cricket ball", "cricket stadium packed crowd floodlights"],
    "basketball": ["basketball player slam dunk rim", "basketball swishing through net hoop", "indoor basketball arena game lights"],
    "tennis": ["tennis player serving ball court", "slow motion tennis racket ball impact", "wimbledon grass tennis court match"],
    "boxing": ["boxer punching heavy bag gym sweat", "boxing match ring fighters punch", "boxer gloves raised victory ring"],
    "boxer": ["boxer shadowboxing ring intense", "heavyweight boxer training sweat", "boxer hands wrapped fighter focus"],
    "gym": ["athlete lifting heavy barbell gym", "intense gym workout dumbbell training", "fitness athlete training gym weights"],
    "workout": ["crossfit athlete kettlebell swing", "intense workout sweat fitness gym", "athlete doing pull ups gym bar"],
    "khel": ["professional stadium sports match", "athlete celebrating victory championship", "running track sprint race"],
    "khiladi": ["athletic champion celebrating trophy", "athlete running sprinting finish line", "sports player intense focus"],
    "kushti": ["wrestling match arena combat", "traditional wrestlers grappling sand", "intense wrestling grapple match"],

    # Food, Cooking & Culinary (1000+ Topics)
    "food": ["delicious gourmet dish plated fine dining", "fresh colorful organic vegetables market", "steaming hot food skillet restaurant"],
    "chef": ["professional chef slicing meat kitchen", "master chef plating gourmet dish tweezers", "chef tossing vegetables flaming pan"],
    "cooking": ["sizzling steak on cast iron grill flames", "stir fry cooking high heat wok flames", "boiling fresh pasta garlic olive oil"],
    "steak": ["juicy ribeye steak grilling open flame", "chef slicing medium rare steak board", "sizzling beef steak rosemary butter"],
    "pizza": ["wood fired pizza oven bubbling cheese", "fresh pizza crust spinning flour air", "stretching hot cheese pizza slice"],
    "coffee": ["barista pouring latte art espresso", "roasted coffee beans falling grinder", "steaming cup of black coffee morning"],
    "restaurant": ["busy fine dining restaurant kitchen", "romantic restaurant dinner candlelight", "outdoor cafe terrace european street"],
    "khana": ["delicious gourmet dish plated fine dining", "steaming hot food skillet restaurant", "traditional feast colorful dishes table"],
    "pakanay": ["chef tossing vegetables flaming pan", "sizzling meat cooking pan flames", "stirring rich aromatic curry pot"],
    "chai": ["traditional hot tea pouring cup steam", "steaming milk tea boiling kettle", "cozy teacup morning sunlight window"],

    # Travel, Wonders & Famous Cities (1000+ Topics)
    "travel": ["backpacker standing mountain vista sunrise", "traveler walking ancient cobblestone street", "tropical turquoise beach vacation"],
    "paris": ["eiffel tower aerial paris sunset", "seine river cruise boats paris", "champs elysees paris arch monument"],
    "dubai": ["burj khalifa dubai skyline aerial", "dubai marina luxury yachts night", "desert safari dune bashing dubai"],
    "tokyo": ["tokyo shibuya crossing busy night", "tokyo neon lights rain reflections", "tokyo tower skyline aerial sunset"],
    "island": ["tropical island aerial turquoise lagoon", "exotic maldives water villas ocean", "palm trees white sand beach paradise"],
    "beach": ["white sand tropical beach clear water", "gentle ocean waves breaking shore", "golden sunset tropical beach hammock"]
}



def auto_detect_niche(text: str, current_niche: str = "") -> str:
    """
    Intelligently infers niche/topic if user forgot to select one, or selected 'General'/'Default'/'Auto'
    or left the legacy 'Motivation Psychology' default while narrating military/conflict/other topics.
    Analyzes vocabulary across semantic topic clusters including Roman Urdu and phonetic spellings.
    """
    cleaned_niche = str(current_niche or "").strip().lower()
    text_lower = (text or "").lower()
    if not text_lower.strip():
        return current_niche or "General"

    is_unselected = cleaned_niche in ("general", "default", "auto", "none", "", "select niche")

    # If user explicitly selected any specific niche, ALWAYS RESPECT USER SELECTION 100%!
    if not is_unselected:
        return current_niche

    # 1. Military, Defense & War (English, Urdu, Roman Urdu, and common phonetic terms)
    mil_markers = [
        "military", "soldier", "soldiers", "army", "fauj", "fauji", "jang", "war", "missile", "missiles",
        "blastoc", "misile", "tank", "tanks", "bomb", "bombs", "attack", "strike", "defense", "radar",
        "fighter jet", "aircraft", "combat", "navy", "air force", "battlefield", "weapon", "weapons",
        "artillery", "troops", "infantry", "patrol", "conflict", "invasion", "tactical", "dhamaka", "blast",
        "tabahi", "tayaray", "hathyar", "nuclear", "warhead", "pentagon", "frontline", "airforce", "warship"
    ]
    if any(re.search(r'\b' + re.escape(w) + r'\b', text_lower) for w in mil_markers):
        return "Military & Defense"

    # 2. Sci-Fi & Space (Requires unambiguous astronomical/cosmic terms to prevent false positives from generic words like 'space' or 'stars')
    space_markers = [
        "outer space", "deep space", "galaxy", "galaxies", "astronaut", "nasa", "cosmos", "universe",
        "nebula", "blackhole", "black hole", "telescope", "mars", "solar system", "satellite",
        "asteroid", "meteor", "comet", "supernova", "exoplanet", "khala", "sayyara", "milky way"
    ]
    if any(re.search(r'\b' + re.escape(w) + r'\b', text_lower) for w in space_markers):
        return "Sci-Fi & Space"

    # 3. Wildlife Predators & Animals
    animal_markers = [
        "tiger", "tigers", "lion", "lions", "eagle", "eagles", "shark", "sharks", "whale", "whales",
        "elephant", "elephants", "cheetah", "wolf", "wolves", "bear", "bears", "leopard", "panther",
        "crocodile", "alligator", "snake", "snakes", "cobra", "python", "gorilla", "jaguar", "rhino",
        "predator", "prey", "hunt", "hunting", "animal", "animals", "creature", "beast", "wildlife", "safari",
        "sher", "cheeta", "baagh", "bagh", "janwar", "shikar", "saanp", "hathi", "bheriya", "magarmach",
        "dolphin", "dolphins", "octopus", "orca", "penguin", "penguins", "owl", "hawk", "falcon", "vulture",
        "chil", "baaz", "parinda", "machli", "hiran", "jungle"
    ]
    if any(re.search(r'\b' + re.escape(w) + r'\b', text_lower) for w in animal_markers):
        return "Wildlife Predators & Oceans"

    # 4. History & Ancient Empires
    hist_markers = [
        "ancient rome", "ancient egypt", "colosseum", "pyramids", "pyramid", "pharaoh", "medieval castle",
        "ottoman empire", "ottoman", "sultan", "gladiator", "sparta", "ancient greece", "viking", "vikings",
        "caesar", "emperor", "dynasty", "samurai", "ninja", "mongol", "knights", "archaeology", "civilization",
        "tareekh", "qadeem", "badshah", "saltanat", "ahraam", "mehal", "qila", "talwar", "sipahi", "khandar"
    ]
    if any(re.search(r'\b' + re.escape(w) + r'\b', text_lower) for w in hist_markers):
        return "History & Empires"

    # 5. Crime & Mystery
    crime_markers = [
        "detective", "crime scene", "murder mystery", "serial killer", "fbi investigation", "police",
        "handcuffs", "prison", "prisoner", "jail", "courtroom", "judge", "gavel", "interrogation",
        "forensic", "fingerprint", "robbery", "heist", "bank vault", "surveillance", "mafia", "gangster",
        "jurm", "mujrim", "qaid", "adalat", "qatil", "qatal", "chor", "daku", "tehqeeqat"
    ]
    if any(re.search(r'\b' + re.escape(w) + r'\b', text_lower) for w in crime_markers):
        return "Crime & Mystery"

    # 6. Horror & Paranormal
    horror_markers = [
        "horror", "haunted house", "creepy", "ghost", "ghosts", "paranormal", "graveyard", "cemetery",
        "witchcraft", "vampire", "monster", "demonic", "nightmare", "eerie", "abandoned house",
        "bhoot", "chudail", "darawna", "khauf", "qabristan", "saya", "khofnak"
    ]
    if any(re.search(r'\b' + re.escape(w) + r'\b', text_lower) for w in horror_markers):
        return "Horror & Paranormal"

    # 7. Automotive & Supercars
    auto_markers = [
        "supercar", "supercars", "ferrari", "lamborghini", "formula 1", "racing track", "drifting",
        "sports car", "hypercar", "speedometer", "motorcycle", "cockpit", "airplane", "helicopter",
        "gari", "jahaz", "raftar", "tayara"
    ]
    if any(re.search(r'\b' + re.escape(w) + r'\b', text_lower) for w in auto_markers):
        return "Automotive & Supercars"

    # 8. Science & Engineering / Medicine
    sci_markers = [
        "dna", "genetics", "microscope", "bacteria", "cells", "surgery", "surgeon", "laboratory",
        "quantum physics", "chemistry", "molecules", "pandemic", "virus", "vaccine",
        "dimagh", "sehat", "ilaj", "beemari", "khoon", "jaraseem"
    ]
    if any(re.search(r'\b' + re.escape(w) + r'\b', text_lower) for w in sci_markers):
        return "Science & Engineering"

    # 9. Finance & Wealth
    fin_markers = [
        "crypto", "bitcoin", "stocks", "trading", "investment", "finance", "dollar", "dollars",
        "wealth", "billionaire", "millionaire", "stock market", "wall street", "gold bars",
        "paisa", "paise", "daulat", "ameer", "khazana", "tijarat", "karobar"
    ]
    if any(re.search(r'\b' + re.escape(w) + r'\b', text_lower) for w in fin_markers):
        return "Finance & Wealth"

    # 10. Tech & AI
    tech_markers = [
        "artificial intelligence", "machine learning", "coding", "software engineer", "cybersecurity",
        "neural network", "hacker", "cyber attack", "servers", "data center", "robot", "robotics", "humanoid"
    ]
    if any(re.search(r'\b' + re.escape(w) + r'\b', text_lower) for w in tech_markers):
        return "Tech & AI"

    # 11. Food & Culinary
    food_markers = [
        "chef", "cooking", "recipe", "gourmet", "restaurant", "steak", "pizza", "barista", "bakery",
        "khana", "pakanay", "chai"
    ]
    if any(re.search(r'\b' + re.escape(w) + r'\b', text_lower) for w in food_markers):
        return "Food & Culinary"

    # 12. Fitness & Health
    fit_markers = [
        "workout", "bodybuilding", "barbell", "dumbbell", "biceps", "cardio", "gym workout",
        "fitness training", "crossfit", "athlete", "boxing gym"
    ]
    if any(re.search(r'\b' + re.escape(w) + r'\b', text_lower) for w in fit_markers):
        return "Fitness & Health"

    # 13. Travel & Adventure
    travel_markers = [
        "traveling", "vacation", "tourist", "eiffel tower", "burj khalifa", "shibuya tokyo", "swiss alps",
        "tropical island", "beach resort"
    ]
    if any(re.search(r'\b' + re.escape(w) + r'\b', text_lower) for w in travel_markers):
        return "Travel & Adventure"

    # 14. Gaming & Esports
    gaming_markers = [
        "gaming", "esports", "gamer", "videogame", "gameplay", "streamer", "cyberpunk gaming"
    ]
    if any(re.search(r'\b' + re.escape(w) + r'\b', text_lower) for w in gaming_markers):
        return "Gaming & Esports"

    # 15. Nature & Scenery
    nat_markers = [
        "waterfall", "rainforest", "mountain summit", "grand canyon", "scenic landscape", "volcano", "earthquake"
    ]
    if any(re.search(r'\b' + re.escape(w) + r'\b', text_lower) for w in nat_markers):
        return "Nature & Wildlife"

    # 16. Stoicism & Philosophy
    stoic_markers = [
        "stoic", "stoicism", "marcus aurelius", "seneca", "epictetus", "philosophy", "marble statue"
    ]
    if any(re.search(r'\b' + re.escape(w) + r'\b', text_lower) for w in stoic_markers):
        return "Stoicism & Philosophy"

    # 17. Motivation Psychology
    mot_markers = [
        "discipline", "mindset", "focus on goals", "overcoming adversity", "procrastination", "motivation",
        "success habit", "inner demons", "stay hard", "relentless", "soch", "hosla", "himmat", "mehnat"
    ]
    if any(re.search(r'\b' + re.escape(w) + r'\b', text_lower) for w in mot_markers):
        return "Motivation Psychology"

    return "General"


def build_scenes(
    transcription: Dict[str, Any],
    niche: str = "General",
    editorial_direction: Optional[Dict[str, Any]] = None,
    max_scene_duration: Optional[float] = None,
    generation_mode: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Takes transcription data and builds structured sentence-level scene objects.
    Each scene corresponds to a single spoken sentence or natural 3-5s visual thought,
    preventing multi-sentence spillage and ensuring 1-to-1 visual-caption harmony.
    Applies editorial direction (pacing multiplier and climax scene tagging).
    """
    settings = load_settings()
    if not generation_mode:
        generation_mode = settings.get("generation_mode", "niche")
    gen_mode = str(generation_mode or "niche").strip().lower()

    editorial = editorial_direction or {}
    pacing_mult = float(editorial.get("pacing_multiplier", 1.0))
    climax_idx = editorial.get("climax_scene_index")

    # Auto-detect niche from transcript ONLY if user didn't choose or left as General/Default/Auto
    full_transcript = transcription.get("text", "")
    if not full_transcript and transcription.get("words"):
        full_transcript = " ".join(w.get("word", "") for w in transcription["words"])
    cleaned_niche = str(niche or "").strip().lower()
    if cleaned_niche in ("general", "default", "auto", "none", "", "select niche"):
        detected_niche = auto_detect_niche(full_transcript, niche)
        if detected_niche and detected_niche != niche:
            print(f"[SceneAnalyzer] Auto-detected niche '{detected_niche}' from voiceover script (was '{niche}')")
            niche = detected_niche

    total_dur = float(transcription.get("duration", 30.0))
    segments = transcription.get("segments", [])

    # 1. Gather all micro-timestamped words
    all_words = []
    if transcription.get("words"):
        for w in transcription["words"]:
            word_str = w.get("word", "").strip()
            if word_str:
                all_words.append({
                    "word": word_str,
                    "start": float(w.get("start", 0)),
                    "end": float(w.get("end", 0))
                })
    if not all_words:
        for seg in segments:
            for w in seg.get("words", []):
                word_str = w.get("word", "").strip()
                if word_str:
                    all_words.append({
                        "word": word_str,
                        "start": float(w.get("start", 0)),
                        "end": float(w.get("end", 0))
                    })

    # 2. Intelligent Word & Sentence Boundary Detection
    if all_words:
        sentence_groups = []
        current_group = []

        for i, w in enumerate(all_words):
            current_group.append(w)
            word_text = w["word"].strip()

            # Punctuation boundary (. ! ? ; : but not titles like Mr., Dr.)
            has_period = bool(re.search(r'[.!?]$', word_text)) and not bool(re.search(r'^(?:Mr|Mrs|Ms|Dr|Prof|vs|etc|e\.g|i\.e)\.$', word_text, re.I))
            has_semicolon = bool(re.search(r'[;:]$', word_text))

            # Speech pause boundary (speaker breathed or paused > 0.45s)
            has_pause = False
            if i < len(all_words) - 1:
                next_w = all_words[i + 1]
                if (next_w["start"] - w["end"]) >= 0.45:
                    has_pause = True

            group_duration = w["end"] - current_group[0]["start"]

            # Dynamic pacing: split long sentences (>= 5.2s scaled by pacing_multiplier) at natural commas or pauses
            has_comma = bool(re.search(r'[,]$', word_text))
            split_threshold = max(3.0, 5.2 * pacing_mult)
            is_pacing_split = (group_duration >= split_threshold and (has_comma or has_pause))
            overlong_threshold = max(4.5, 7.0 * pacing_mult)
            is_overlong = (group_duration >= overlong_threshold and len(current_group) >= 5)
            # A true sentence/clause split condition: requires punctuation, at least 3 words and duration >= 2.0s
            is_punct_split = (has_period or has_semicolon) and len(current_group) >= 3 and group_duration >= 2.0
            # A speech pause boundary: only split if group already has at least 5 words and duration >= 2.8s
            is_pause_split = has_pause and len(current_group) >= 5 and group_duration >= 2.8
            is_last_word = (i == len(all_words) - 1)

            if is_punct_split or is_pause_split or is_pacing_split or is_overlong or is_last_word:
                # Minimum duration filter: scenes should be at least 2.0s and >= 3 words to avoid jarring flicker
                if (group_duration >= 2.0 and len(current_group) >= 3) or is_last_word or len(sentence_groups) == 0:
                    sentence_groups.append(current_group)
                    current_group = []

        if current_group:
            if sentence_groups:
                sentence_groups[-1].extend(current_group)
            else:
                sentence_groups.append(current_group)

        # NLP Fallback: If punctuation detection found only 1 giant group (Whisper
        # returned words without any punctuation), and transcript is long, use regex sentence splitting.
        full_text = " ".join(w["word"] for w in all_words)
        has_internal_punct = bool(re.search(r'[.!?]', full_text[:-1]))
        if len(sentence_groups) <= 1 and (not has_internal_punct and len(all_words) > 10 or len(all_words) > 20):
            nlp_sentences = [s.strip() for s in re.split(r'(?<=[.!?;])\s+', full_text) if s.strip()]
            if len(nlp_sentences) <= 1:
                nlp_sentences = _split_by_word_count(all_words, target_words=5)

            if len(nlp_sentences) > 1:
                print(f"[SceneAnalyzer] NLP fallback: punctuation-free transcript, split into {len(nlp_sentences)} sentences via regex")
                sentence_groups = _map_sentences_to_words(nlp_sentences, all_words)

        # Post-pass micro-fragment merging:
        # Guarantee: ALWAYS run after all segmentation and NLP paths to merge any
        # fragments (< 4 words or < 2.2s duration) into the preceding scene group.
        # This completely eliminates isolated 1-word scenes like 'you?...' or 'Right?'
        sentence_groups = _merge_micro_fragments(sentence_groups)

        # 3. Build gapless, continuous scene timestamps
        scenes = []
        for idx, grp in enumerate(sentence_groups):
            grp_text = " ".join(x["word"] for x in grp).strip()
            start = round(grp[0]["start"], 2)
            if idx == 0 and start < 1.2:
                start = 0.0

            if idx < len(sentence_groups) - 1:
                end = round(sentence_groups[idx + 1][0]["start"], 2)
            else:
                end = round(max(grp[-1]["end"], total_dur), 2)

            dur = round(max(0.5, end - start), 2)
            context_window = ""
            if idx > 0:
                context_window += " " + " ".join(x["word"] for x in sentence_groups[idx - 1])
            if idx < len(sentence_groups) - 1:
                context_window += " " + " ".join(x["word"] for x in sentence_groups[idx + 1])
            tags = _extract_tags_rulebased(grp_text, niche, surrounding_context=context_window.strip())

            scenes.append({
                "id": idx,
                "scene_number": idx + 1,
                "niche": niche,
                "start": start,
                "end": end,
                "duration": dur,
                "text": grp_text,
                "words": grp,
                "search_tags": tags,
                "selected_tag": tags[0] if tags else f"{niche} cinematic",
                "video_clip": None,
                "status": "pending",
                "is_climax": (climax_idx is not None and idx == climax_idx)
            })
    else:
        # Fallback if words array was empty: split segments by sentence regex
        scenes = []
        for i, seg in enumerate(segments):
            seg_text = seg.get("text", "").strip()
            start = float(seg.get("start", 0))
            end = float(seg.get("end", 0))
            dur = round(max(0.5, end - start), 2)
            tags = _extract_tags_rulebased(seg_text, niche)
            scenes.append({
                "id": i,
                "scene_number": i + 1,
                "niche": niche,
                "start": start,
                "end": end,
                "duration": dur,
                "text": seg_text,
                "words": seg.get("words", []),
                "search_tags": tags,
                "selected_tag": tags[0] if tags else f"{niche} cinematic",
                "video_clip": None,
                "status": "pending",
                "is_climax": (climax_idx is not None and i == climax_idx)
            })

    # Validate climax scene flag
    if climax_idx is not None and scenes:
        valid_climax = max(0, min(int(climax_idx), len(scenes) - 1))
        for i, sc in enumerate(scenes):
            sc["is_climax"] = (i == valid_climax)
    else:
        for sc in scenes:
            if "is_climax" not in sc:
                sc["is_climax"] = False

    # Apply pacing multiplier to max scene duration cap if specified
    if max_scene_duration is not None:
        effective_max = round(float(max_scene_duration) * pacing_mult, 2)
        for sc in scenes:
            if sc.get("duration", 0) > effective_max:
                sc["duration"] = effective_max

    # AI Enhancement if API key is provided (Gemini, Groq, or OpenAI)
    gemini_key = settings.get("gemini_api_key", "").strip()
    gemini_keys = settings.get("gemini_api_keys") or ([gemini_key] if gemini_key else [])
    groq_keys = settings.get("groq_api_keys") or ([settings.get("groq_api_key")] if settings.get("groq_api_key") else [])
    openai_key = settings.get("openai_api_key", "").strip()
    if (gemini_keys or groq_keys or openai_key) and scenes:
        try:
            enhanced_data = _enhance_tags_with_ai(scenes, niche, gemini_keys, groq_keys, openai_key, generation_mode=gen_mode)
            niche_clean_check = str(niche or "").lower()
            is_niche_mode = (gen_mode != "voiceover")
            is_space_target = is_niche_mode and any(k in niche_clean_check for k in ("space", "sci-fi", "cosmos", "astronomy"))
            is_mil_target = is_niche_mode and any(k in niche_clean_check for k in ("military", "war", "defense", "conflict"))
            is_mot_target = is_niche_mode and any(k in niche_clean_check for k in ("motivation", "stoic", "discipline", "mindset", "success"))

            space_bad_tokens = {"playground", "children", "child", "bedroom", "sleeping", "bed", "alarm clock", "wallet", "dollar", "cash", "money", "cooking", "kitchen", "makeup", "beach party", "gym", "workout", "hospital", "patient"}
            mil_bad_tokens = {"boxer", "boxing", "gym", "workout", "fitness", "swimming", "beach", "wedding", "makeup", "playground", "bedroom"}
            mot_bad_tokens = {"space", "galaxy", "astronaut", "nebula", "planet", "alien", "ufo", "recipe", "cooking", "makeup"}

            default_space_flavors = ["deep space galaxy nebula", "astronaut walking planet surface", "hubble telescope cosmos 4k", "spacewalk earth orbit satellite", "futuristic sci-fi spacecraft"]

            for sc_idx, (sc, item) in enumerate(zip(scenes, enhanced_data)):
                tags = []
                callout = None
                emp_word = None
                if isinstance(item, list):
                    tags = [str(t).strip() for t in item if t]
                elif isinstance(item, dict):
                    raw_tags = item.get("search_tags", [])
                    tags = [str(t).strip() for t in raw_tags if t]
                    callout = item.get("callout_text")
                    emp_word = item.get("emphasis_word")

                if is_space_target:
                    clean_tags = [t for t in tags if not any(bad in t.lower() for bad in space_bad_tokens)]
                    has_space_kw = any(any(sk in t.lower() for sk in ("space", "galaxy", "nebula", "astronaut", "planet", "cosmos", "star", "orbit", "telescope", "sci-fi", "alien", "rocket")) for t in clean_tags)
                    if not has_space_kw or len(clean_tags) < 2:
                        flavor = default_space_flavors[sc_idx % len(default_space_flavors)]
                        if flavor not in clean_tags:
                            clean_tags.insert(0, flavor)
                    tags = clean_tags if clean_tags else [default_space_flavors[sc_idx % len(default_space_flavors)]]
                elif is_mil_target:
                    clean_tags = [t for t in tags if not any(bad in t.lower() for bad in mil_bad_tokens)]
                    if clean_tags:
                        tags = clean_tags
                elif is_mot_target:
                    clean_tags = [t for t in tags if not any(bad in t.lower() for bad in mot_bad_tokens)]
                    if clean_tags:
                        tags = clean_tags

                if tags:
                    sc["search_tags"] = tags
                    sc["selected_tag"] = tags[0]
                if callout is not None:
                    sc["raw_callout_text"] = callout
                if emp_word is not None:
                    sc["emphasis_word"] = emp_word
        except Exception as e:
            print(f"[SceneAnalyzer] AI tag enhancement notice: {e}")

    # Prioritize & Rate-Limit Callouts (~1 in every 4-5 scenes, prioritizing is_climax)
    _apply_callouts_prioritization(scenes)

    # Match emphasis words with Whisper word timestamps and check boundary distances
    _match_emphasis_words_with_timestamps(scenes)

    return scenes


def _split_by_word_count(all_words: list, target_words: int = 5) -> List[str]:
    """Fallback splitter: groups words into chunks of ~target_words for visual pacing."""
    sentences = []
    chunk = []
    for w in all_words:
        chunk.append(w["word"])
        if len(chunk) >= target_words:
            sentences.append(" ".join(chunk))
            chunk = []
    if chunk:
        if sentences and len(chunk) < 3:
            sentences[-1] += " " + " ".join(chunk)
        else:
            sentences.append(" ".join(chunk))
    return sentences


def _map_sentences_to_words(sentences: List[str], all_words: list) -> list:
    """Maps regex-split sentences back to word-level timestamp groups."""
    groups = []
    word_idx = 0
    for sent in sentences:
        sent_words = sent.split()
        grp = []
        matched = 0
        while word_idx < len(all_words) and matched < len(sent_words):
            grp.append(all_words[word_idx])
            word_idx += 1
            matched += 1
        if grp:
            groups.append(grp)
    # Attach any remaining words to the last group
    if word_idx < len(all_words) and groups:
        groups[-1].extend(all_words[word_idx:])
    return groups


def _merge_micro_fragments(groups: list) -> list:
    """
    Merges any orphaned fragments (< 4 words or < 2.2s duration) into the preceding group
    so scenes never have isolated 1-word text like 'you?...' or 'Right?'.
    """
    if len(groups) <= 1:
        return groups

    merged = []
    for grp in groups:
        if not grp:
            continue
        dur = float(grp[-1].get("end", 0)) - float(grp[0].get("start", 0))
        word_count = len(grp)
        # If this group is a tiny fragment (<= 2 words, or < 4 words with short duration < 2.0s, or dur < 1.4s):
        is_fragment = (word_count <= 2) or (word_count < 4 and dur < 2.0) or (dur < 1.4)
        if is_fragment and merged:
            merged[-1].extend(grp)
        else:
            merged.append(grp)

    # Check if the very last group became too small
    if len(merged) > 1:
        last_dur = float(merged[-1][-1].get("end", 0)) - float(merged[-1][0].get("start", 0))
        if (len(merged[-1]) <= 2) or (len(merged[-1]) < 4 and last_dur < 2.0) or (last_dur < 1.4):
            last = merged.pop()
            merged[-1].extend(last)

    return merged if merged else groups


# Cross-domain ambiguous words that mean DIFFERENT physical visuals depending on niche/topic context.
# Without context-aware disambiguation, Pexels returns boxing for "fight" in a military script, or office for "hunt" in wildlife.
CONTEXT_SENSITIVE_WORDS = {
    "fight": {
        "military": ["military combat soldiers battlefield", "tactical armed troops fighting"],
        "wildlife": ["predator animals fighting territory", "wild animals aggressive encounter"],
        "history": ["medieval sword battle clash", "ancient warriors shield fight"],
        "sports": ["boxing match ring fighters", "mma fighter cage combat"],
        "motivation": ["person overcoming obstacles mountain", "lone figure stormy cliff"],
        "default": ["ancient warriors battle clash", "epic war soldiers charging"]
    },
    "fighting": {
        "military": ["soldiers fighting battlefield war", "tactical infantry combat troops"],
        "wildlife": ["wild animals aggressive clash", "predators territorial fight"],
        "history": ["medieval knights sword combat", "gladiators fighting arena"],
        "sports": ["boxers punching match ring", "martial arts fighting duel"],
        "motivation": ["determined person pushing through", "overcoming challenge mountain climb"],
        "default": ["ancient warriors battle clash", "soldiers charging battlefield"]
    },
    "training": {
        "military": ["military tactical training boot camp", "soldiers armed forces drill"],
        "fitness": ["athlete training gym weights", "runner training outdoor track"],
        "sports": ["soccer team training pitch", "boxer training heavy bag gym"],
        "default": ["professional training workshop classroom", "students learning practice"]
    },
    "target": {
        "military": ["military radar target crosshairs", "missile target precision strike"],
        "business": ["business goal target chart", "dart hitting bullseye target"],
        "sports": ["archery target precision aim", "shooting range target paper"],
        "default": ["archery target precision aim", "crosshairs focus target"]
    },
    "strike": {
        "military": ["military airstrike explosion", "missile strike precision explosion"],
        "nature": ["lightning strike dramatic storm", "lightning bolt dark clouds"],
        "sports": ["baseball player strike pitch", "bowling ball strike pins"],
        "default": ["lightning strike dramatic sky", "workers protest strike rally"]
    },
    "attack": {
        "military": ["military armed attack tactical", "airstrike explosion attack"],
        "wildlife": ["predator animal attacking prey", "shark attacking underwater"],
        "tech": ["cyber attack hacker terminal code", "cyber security breach warning"],
        "default": ["military armed attack tactical", "cyber security hacker screen"]
    },
    "attacks": {
        "military": ["military airstrikes tactical explosions", "combat soldiers attack frontline"],
        "wildlife": ["wild predator attacking prey", "shark attacks underwater ocean"],
        "tech": ["cyber attacks firewall data breach", "hacker multiple terminals cyber attack"],
        "default": ["military airstrikes explosions", "tactical offensive soldiers"]
    },
    "hunt": {
        "wildlife": ["lion hunting prey savannah", "predator stalking prey wilderness"],
        "military": ["military search operation tactical", "soldiers searching terrain patrol"],
        "crime": ["detective tracking suspect night", "police manhunt search operation"],
        "history": ["primitive tribal hunters bows", "ancient hunters tracking forest"],
        "default": ["eagle hunting prey aerial", "wolf pack hunting forest"]
    },
    "hunting": {
        "wildlife": ["predator stalking prey wilderness", "lion hunting gazelle savannah"],
        "military": ["tactical patrol soldiers searching", "sniper scanning territory binoculars"],
        "default": ["eagle hunting prey forest", "wolf hunting deer wilderness"]
    },
    "power": {
        "military": ["military superpower weapons display", "aircraft carrier naval power"],
        "tech": ["nuclear power plant energy", "electric power grid station"],
        "science": ["nuclear reactor atomic power", "high voltage electric spark"],
        "automotive": ["supercar horsepower engine revving", "twin turbo engine speed power"],
        "motivation": ["powerful leader speaking podium", "fist raised determination silhouette"],
        "default": ["lightning bolt electric power", "nuclear reactor energy plant"]
    },
    "battle": {
        "military": ["military battlefield soldiers fighting", "war combat armored forces"],
        "history": ["ancient roman army battle", "medieval castle siege battle"],
        "default": ["medieval castle siege battle", "ancient armies clash battlefield"]
    },
    "struggle": {
        "military": ["soldiers marching harsh battlefield", "military endurance combat"],
        "motivation": ["person climbing steep mountain", "lone figure rain walking"],
        "default": ["person climbing steep mountain", "overcoming obstacles dark tunnel"]
    },
    "warrior": {
        "military": ["armed combat soldier warrior", "tactical special forces warrior"],
        "history": ["ancient samurai warrior armor", "medieval knight armor broadsword", "viking warrior axe battle"],
        "default": ["ancient samurai warrior armor", "medieval knight armor sword"]
    },
    "destroy": {
        "military": ["military bombing explosion rubble", "missile destroying target explosion"],
        "disaster": ["earthquake destruction buildings rubble", "tornado destruction flying debris"],
        "default": ["demolition building explosion", "earthquake destruction rubble"]
    },
    "kill": {
        "wildlife": ["predator catching prey hunt", "lion killing prey savannah"],
        "military": ["military sniper precision shot", "combat soldiers tactical firing"],
        "crime": ["detective inspecting murder scene", "police crime tape rain night"],
        "default": ["dramatic cinematic suspense dark", "shadowy figure dark alley"]
    },
    "speed": {
        "automotive": ["supercar racing track speed", "formula one car blur", "speedometer needle accelerating"],
        "wildlife": ["cheetah running fast savannah", "falcon diving speed aerial"],
        "aviation": ["supersonic fighter jet speed", "commercial jet flying fast clouds"],
        "sports": ["sprinter running track fast", "athlete sprint finish line"],
        "default": ["fast motion blur highway", "speedometer accelerating dashboard"]
    },
    "fall": {
        "motivation": ["person falling getting back up", "determined figure rising after fall"],
        "history": ["fall of ancient roman empire", "crumbling historical stone ruins"],
        "military": ["soldier falling battlefield combat", "building collapsing explosion"],
        "nature": ["autumn leaves falling slow motion", "waterfall flowing scenic nature"],
        "default": ["autumn leaves falling trees", "waterfall flowing scenic nature"]
    },
    "lead": {
        "military": ["military commander leading troops", "officer directing soldiers battle"],
        "business": ["ceo leading boardroom meeting", "executive presenting strategy team"],
        "history": ["ancient king leading army", "emperor marching troops"],
        "default": ["leader walking ahead group", "person leading team confident"]
    },
    "mining": {
        "finance": ["bitcoin mining server farm", "cryptocurrency mining rig"],
        "crypto": ["bitcoin mining server farm", "crypto mining graphics cards"],
        "industry": ["underground mine workers coal", "heavy mining excavator quarry"],
        "default": ["underground mine workers coal", "gold mining excavation"]
    },
    "defense": {
        "military": ["air defense radar missile system", "anti aircraft missile battery"],
        "sports": ["basketball team defense guard", "soccer defender blocking shot"],
        "law": ["courtroom lawyer defense argument", "defense attorney trial jury"],
        "cyber": ["cyber security defense shield glowing", "firewall security data protection"],
        "default": ["military air defense system", "security shield protection"]
    },
    "virus": {
        "medical": ["microscopic virus cells mutating", "viral infection 3d animation", "pandemic medical research lab"],
        "science": ["microscopic biological virus 3d", "laboratory virus vaccine research"],
        "tech": ["computer virus ransomware screen", "cyber attack hacker malware terminal"],
        "default": ["virus microscope 3d animation", "medical viral infection cells"]
    },
    "cell": {
        "medical": ["microscopic living human cells", "cell division biology microscope"],
        "science": ["microscope specimen biological cells", "cellular dna research lab"],
        "crime": ["prison iron cell bars corridor", "inmate behind jail cell door"],
        "tech": ["smartphone mobile screen touch", "cell tower transmission antenna"],
        "default": ["microscopic biological cells 3d", "laboratory microscope view"]
    },
    "cells": {
        "medical": ["microscopic living human cells", "human blood cells microscope"],
        "science": ["cellular division biology lab", "microscopic organisms swimming"],
        "crime": ["prison cell corridor guard tower", "jail cells inmates walking"],
        "default": ["microscopic cells biology 3d", "living cells laboratory"]
    },
    "race": {
        "automotive": ["formula 1 cars racing track", "supercars racing highway speed"],
        "sports": ["runners sprinting 100m track", "marathon race crowd running"],
        "animals": ["wild horses galloping fast", "horse race track jockeys"],
        "default": ["formula 1 cars racing track", "athlete sprint race running"]
    },
    "racing": {
        "automotive": ["formula 1 race car speed blur", "sports car drifting track"],
        "sports": ["sprinters sprinting track finish", "swimming race olympic pool"],
        "animals": ["horses racing galloping turf", "greyhound racing track"],
        "default": ["formula 1 race car speed blur", "sports car racing track"]
    },
    "crash": {
        "automotive": ["car crash test slow motion", "vehicle collision impact dummy"],
        "finance": ["stock market crash red graph", "wall street traders panicking crash"],
        "aviation": ["airplane emergency landing runway", "plane crash wreckage investigation"],
        "tech": ["computer blue screen crash error", "server system crash warning"],
        "default": ["car crash test slow motion", "stock market crash red chart"]
    },
    "wave": {
        "nature": ["giant ocean tsunami wave", "massive surf wave ocean curling"],
        "science": ["sound wave frequency audio", "electromagnetic wave radiation 3d"],
        "military": ["wave of soldiers charging battlefield", "naval warship cutting ocean wave"],
        "default": ["ocean waves crashing shore", "giant surf wave ocean"]
    },
    "waves": {
        "nature": ["ocean waves crashing rocks sunset", "aerial ocean turquoise waves shore"],
        "science": ["electromagnetic radio waves 3d", "oscilloscope sound waves glowing"],
        "default": ["ocean waves breaking shoreline", "aerial turquoise ocean waves"]
    },
    "bank": {
        "finance": ["massive steel bank vault door", "bank building financial district", "bank teller cash transactions"],
        "nature": ["lush green river bank trees", "foggy lake bank peaceful nature"],
        "default": ["bank vault door safe boxes", "financial district bank building"]
    },
    "ring": {
        "sports": ["boxing match ring heavy punch", "wrestling ring arena lights"],
        "luxury": ["diamond wedding ring glowing gold", "luxury jewelry diamond ring macro"],
        "default": ["boxing match ring fighters", "diamond wedding ring luxury"]
    },
    "court": {
        "crime": ["courtroom judge gavel trial", "lawyer arguing court jury"],
        "sports": ["basketball court players game", "tennis court clay match"],
        "history": ["ancient royal court king throne", "emperor imperial court nobles"],
        "default": ["courtroom judge gavel trial", "basketball court game lights"]
    },
    "escape": {
        "crime": ["prisoner escaping dark prison wall", "handcuffed convict running night"],
        "wildlife": ["gazelle escaping cheetah chase", "prey animal sprinting predator escape"],
        "disaster": ["people evacuating wildfire disaster", "running escaping collapsing building"],
        "default": ["person escaping dark labyrinth", "running through dark tunnel light"]
    },
    "shadow": {
        "horror": ["creepy silhouette shadow dark wall", "eerie shadow monster lurking"],
        "crime": ["detective silhouette dark alley lamp", "shadowy criminal running night"],
        "stoic": ["lone figure deep shadow sunset", "ancient marble statue dramatic shadow"],
        "default": ["creepy silhouette shadow dark", "mysterious figure dark alley"]
    },
    "shadows": {
        "horror": ["creepy dark shadows moving wall", "eerie shadows misty graveyard"],
        "mystery": ["noir silhouettes shadows rain night", "shadowy figures meeting dark room"],
        "default": ["creepy dark shadows on wall", "long shadows sunset dramatic"]
    },
    "charge": {
        "military": ["cavalry soldiers charging battle", "infantry charging battlefield smoke"],
        "wildlife": ["angry rhino charging dust savannah", "bull charging horn attack"],
        "automotive": ["electric car charging cable plugged", "ev charging station glowing blue"],
        "finance": ["credit card payment terminal tap", "mobile contactless charge card"],
        "default": ["soldiers charging battlefield", "electric car charging battery"]
    },
    "field": {
        "military": ["war combat battlefield soldiers", "trench battlefield smoke fire"],
        "nature": ["lush green wildflower meadow sunlight", "golden wheat field breeze sunset"],
        "sports": ["football soccer stadium field grass", "baseball green field outfield"],
        "science": ["magnetic force field 3d physics", "laser field laboratory experiment"],
        "default": ["lush green wildflower meadow", "battlefield soldiers smoke"]
    },
    "shoot": {
        "military": ["tactical military soldier shooting rifle", "special forces sniper aiming rifle"],
        "sports": ["basketball player shooting hoop", "soccer striker shooting goal"],
        "media": ["cinematographer shooting cinema camera", "film director looking camera monitor"],
        "default": ["tactical soldier shooting rifle", "basketball player shooting basket"]
    },
    "shooting": {
        "military": ["tactical firearms shooting range", "infantry soldiers shooting combat"],
        "space": ["shooting star meteor night sky", "meteor shower night sky timelapse"],
        "sports": ["basketball player shooting hoop court", "archery shooting bullseye target"],
        "default": ["tactical military shooting rifle", "shooting star night sky"]
    }
}


def _resolve_context_word(word: str, niche: str, combined_context: str) -> Optional[List[str]]:
    """Resolves ambiguous words like 'fight', 'hunt', 'power' to context-appropriate stock queries."""
    if word not in CONTEXT_SENSITIVE_WORDS:
        return None
    variants = CONTEXT_SENSITIVE_WORDS[word]
    niche_lower = niche.lower()
    # Find best matching context key
    for ctx_key in variants:
        if ctx_key == "default":
            continue
        if ctx_key in niche_lower or ctx_key in combined_context:
            return variants[ctx_key]
    return variants.get("default")


def _extract_tags_rulebased(text: str, niche: str, surrounding_context: str = "") -> List[str]:
    """Generates visual tags based on text tokens, emotions, niche context, and surrounding sentences."""
    text_lower = text.lower()
    combined_context = (text_lower + " " + surrounding_context.lower()).strip()
    matched_queries = []
    niche_lower = niche.lower()

    # 0. Broad Domain Detection for context sensitivity & clash avoidance
    is_military = any(k in niche_lower for k in ("military", "war", "defense", "conflict", "army")) or any(k in combined_context for k in (
        "military", "soldier", "soldiers", "army", "war", "missile", "missiles", "blastoc", "tank", "tanks",
        "fauj", "fauji", "jang", "attack", "strike", "defense", "radar", "fighter jet", "aircraft", "bomb", "bombs",
        "combat", "navy", "battlefield", "weapon", "weapons", "troops", "infantry", "artillery", "frontline"
    ))
    is_wildlife = any(k in niche_lower for k in ("wildlife", "animal", "predator", "ocean")) or any(k in combined_context for k in (
        "tiger", "tigers", "lion", "lions", "eagle", "eagles", "shark", "sharks", "whale", "whales",
        "elephant", "elephants", "cheetah", "wolf", "wolves", "bear", "bears", "leopard", "crocodile",
        "snake", "gorilla", "predator", "prey", "hunt", "hunting", "sher", "shikar", "janwar", "saanp"
    ))
    is_motivation = any(k in niche_lower for k in ("motivation", "stoic", "discipline", "mindset", "success", "psychology", "growth"))
    is_space = any(k in niche_lower for k in ("space", "sci-fi", "cosmos", "astronomy")) or any(k in combined_context for k in (
        "outer space", "deep space", "galaxy", "galaxies", "astronaut", "nasa", "cosmos", "nebula", "blackhole", "black hole", "telescope", "solar system"
    ))
    is_history = any(k in niche_lower for k in ("history", "empire", "ancient")) or any(k in combined_context for k in (
        "ancient rome", "ancient egypt", "pyramid", "pyramids", "pharaoh", "colosseum", "gladiator", "medieval", "knight", "castle", "ottoman", "sultan", "tareekh", "qadeem"
    ))
    is_crime = any(k in niche_lower for k in ("crime", "mystery", "noir")) or any(k in combined_context for k in (
        "detective", "crime scene", "murder", "police", "handcuffs", "prison", "jail", "courtroom", "judge", "heist", "robbery", "jurm", "mujrim", "qaid"
    ))
    is_horror = any(k in niche_lower for k in ("horror", "paranormal")) or any(k in combined_context for k in (
        "horror", "haunted", "ghost", "ghosts", "creepy", "graveyard", "cemetery", "witch", "vampire", "monster", "nightmare", "bhoot", "chudail", "darawna"
    ))
    is_auto = any(k in niche_lower for k in ("automotive", "supercar", "car")) or any(k in combined_context for k in (
        "supercar", "supercars", "ferrari", "lamborghini", "formula 1", "racing track", "drift", "sports car", "speedometer", "gari", "raftar"
    ))
    is_science = any(k in niche_lower for k in ("science", "engineering", "brain", "medical")) or any(k in combined_context for k in (
        "dna", "genetics", "microscope", "bacteria", "cells", "surgery", "surgeon", "laboratory", "virus", "dimagh", "sehat", "ilaj"
    ))
    is_finance = any(k in niche_lower for k in ("finance", "wealth", "business", "luxury")) or any(k in combined_context for k in (
        "crypto", "bitcoin", "stocks", "trading", "investment", "dollar", "wealth", "billionaire", "millionaire", "paisa", "daulat", "khazana"
    ))

    # Dynamic Niche Overrides ONLY if user had left niche as General or default
    is_unselected_niche = niche_lower in ("general", "default", "auto", "none", "", "select niche")
    if is_unselected_niche:
        if is_military and niche not in ("War & Conflict", "Military & Defense"):
            niche = "Military & Defense"
        elif is_wildlife and niche not in ("Wildlife Predators & Oceans", "Nature & Wildlife"):
            niche = "Wildlife Predators & Oceans"
        elif is_space and niche not in ("Sci-Fi & Space",):
            niche = "Sci-Fi & Space"
        elif is_history and niche not in ("History & Empires",):
            niche = "History & Empires"
        elif is_crime and niche not in ("Crime & Mystery",):
            niche = "Crime & Mystery"
        elif is_horror and niche not in ("Horror & Paranormal",):
            niche = "Horror & Paranormal"

    # Domain Blacklist: words in queries that will make Pexels/Pixabay return WRONG domain clips
    domain_blacklist = set()
    if is_motivation:
        domain_blacklist = {"space", "outer space", "galaxy", "astronaut", "nebula", "solar system", "alien", "ufo", "recipe", "cooking", "wedding", "makeup", "puppy", "kitten"}
    elif is_military:
        domain_blacklist = {"boxer", "boxing", "punching", "gym", "workout", "fitness", "bodybuilding",
                           "crossfit", "yoga", "swimming", "pool", "dance", "ballet", "soccer", "football", "wedding", "makeup"}
    elif is_wildlife:
        domain_blacklist = {"gym", "office", "computer", "keyboard", "desk", "meeting", "boardroom",
                           "boxing", "workout", "trading", "stocks", "wedding", "makeup"}
    elif is_space:
        domain_blacklist = {"gym", "swimming", "pool", "beach", "office", "kitchen", "boxing", "wedding", "makeup", "soccer"}
    elif is_history:
        domain_blacklist = {"laptop", "computer", "smartphone", "modern", "highway", "supercar", "gym", "office cubicle"}
    elif is_crime:
        domain_blacklist = {"cheerful", "beach party", "wedding celebration", "romantic picnic", "happy kids", "cooking recipe"}
    elif is_horror:
        domain_blacklist = {"sunny beach", "happy children", "wedding celebration", "workout gym", "cooking food", "cute puppy"}
    elif is_science:
        domain_blacklist = {"beach party", "nightclub dancing", "sports stadium", "soccer", "fashion runway"}
    elif is_finance:
        domain_blacklist = {"farm tractor", "dirty mud", "barn animals", "kids playground", "beach party"}

    niche_flavor = NICHE_VISUAL_FLAVORS.get(niche, NICHE_VISUAL_FLAVORS.get("General", ["cinematic inspiring 4k"]))

    # 1. Check context-sensitive words FIRST (these override KEYWORD_MAP for ambiguous terms)
    context_resolved_words = set()
    for word in re.findall(r'\b[a-zA-Z]{3,}\b', text_lower):
        resolved = _resolve_context_word(word, niche, combined_context)
        if resolved:
            matched_queries.extend(resolved[:2])
            context_resolved_words.add(word)

    # 2. Check for direct keyword mappings (plural & variation tolerant)
    # SKIP keywords that were already resolved by context-sensitive system above
    has_direct_kw = bool(matched_queries)
    for kw, queries in KEYWORD_MAP.items():
        if kw in context_resolved_words:
            continue  # Already handled by context-aware resolution
        pattern = r'\b' + re.escape(kw) + r'(?:s|es|ing|ed)?\b'
        if re.search(pattern, text_lower):
            # Filter out cross-domain clash terms from queries
            filtered = [q for q in queries if not any(bad in q.lower() for bad in domain_blacklist)] if domain_blacklist else queries
            if filtered:
                shuffled_kws = random.sample(filtered, min(len(filtered), 2))
                matched_queries.extend(shuffled_kws)
                has_direct_kw = True

    # 3. Check surrounding context if current sentence has no direct keyword
    if not has_direct_kw and surrounding_context:
        ctx_lower = surrounding_context.lower()
        for kw, queries in KEYWORD_MAP.items():
            if kw in context_resolved_words:
                continue
            pattern = r'\b' + re.escape(kw) + r'(?:s|es|ing|ed)?\b'
            if re.search(pattern, ctx_lower):
                filtered = [q for q in queries if not any(bad in q.lower() for bad in domain_blacklist)] if domain_blacklist else queries
                if filtered:
                    matched_queries.append(random.choice(filtered))
                    has_direct_kw = True

    # 4. Clean words for salient nouns/verbs
    stop_words = {"this", "that", "with", "from", "have", "been", "were", "what", "here", "there", "they", "your", "will", "would", "could", "should", "about", "thing", "some", "more", "most", "also", "then", "into", "onto", "when", "where", "which"}
    clean_words = [w for w in re.findall(r'\b[a-zA-Z]{4,}\b', text_lower) if w not in stop_words and w not in context_resolved_words]

    # Determine domain aesthetic bias
    if is_motivation:
        domain_bias = "determined motivational"
    elif is_military:
        domain_bias = "military tactical"
    elif is_wildlife:
        domain_bias = "wildlife nature"
    elif is_space:
        domain_bias = "deep space cosmos"
    elif is_history:
        domain_bias = "ancient historical"
    elif is_crime:
        domain_bias = "cinematic crime"
    elif is_horror:
        domain_bias = "dark eerie"
    elif is_auto:
        domain_bias = "supercar speed"
    elif is_science:
        domain_bias = "scientific medical"
    elif is_finance:
        domain_bias = "luxury finance"
    else:
        domain_bias = "cinematic 4k"

    # If direct keyword matched, add clean words as supplementary niche-biased query
    if has_direct_kw and clean_words:
        keyword_phrase = " ".join(clean_words[:2])
        matched_queries.append(f"{keyword_phrase} {domain_bias}")
    elif not has_direct_kw:
        matched_queries.extend(niche_flavor[:3])
        if clean_words:
            matched_queries.append(f"{' '.join(clean_words[:2])} {domain_bias}")

    # 5. Always ensure niche flavor tags are included as strong fallbacks
    for nf in niche_flavor[:2]:
        if nf not in matched_queries:
            matched_queries.append(nf)

    # De-duplicate while preserving priority order
    unique_tags = []
    for q in matched_queries:
        q_clean = q.strip()
        if q_clean and q_clean not in unique_tags:
            unique_tags.append(q_clean)

    return unique_tags[:5]


def _call_gemini_api(prompt: str, gemini_keys: List[str]) -> Optional[str]:
    """Calls Google Gemini API across candidate keys using active production models and JSON response."""
    for key in gemini_keys:
        k_clean = str(key).strip()
        if not k_clean:
            continue
        k_mask = f"...{k_clean[-4:]}" if len(k_clean) >= 4 else k_clean
        for model in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-flash-8b", "gemini-1.5-pro"]:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={k_clean}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.2,
                        "responseMimeType": "application/json"
                    }
                }
                res = requests.post(url, json=payload, timeout=20)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            text_out = parts[0].get("text", "")
                            if text_out:
                                print(f"[SceneAnalyzer] Google Gemini ({model} via key {k_mask}) successfully generated visual tags.")
                                return text_out
                else:
                    print(f"[SceneAnalyzer] Gemini API {model} notice (key {k_mask}): HTTP {res.status_code} - {res.text[:100]}")
            except Exception as e:
                print(f"[SceneAnalyzer] Gemini API connection notice ({model} via {k_mask}): {e}")
                continue
    return None


def _enhance_tags_with_ai(
    scenes: List[Dict[str, Any]],
    niche: str,
    gemini_keys: Optional[List[str]] = None,
    groq_keys: Optional[List[str]] = None,
    openai_key: str = "",
    generation_mode: str = "niche"
) -> List[Dict[str, Any]]:
    """
    Calls Groq (PRIMARY ENGINE across multi-key pool), Gemini (FALLBACK), or OpenAI LLM
    to generate cinematic visual search tags, callout badges, and emphasis zoom words.
    Chunks large scenes (>10) to prevent token truncation and JSON parse errors.
    """
    if not scenes:
        return []

    # Chunk into batches of max 10 scenes to avoid response truncation
    chunk_size = 10
    if len(scenes) > chunk_size:
        all_enhanced = []
        for start_idx in range(0, len(scenes), chunk_size):
            chunk = scenes[start_idx:start_idx + chunk_size]
            sub_results = _enhance_tags_chunk(chunk, niche, gemini_keys, groq_keys, openai_key, generation_mode=generation_mode)
            all_enhanced.extend(sub_results)
        return all_enhanced

    return _enhance_tags_chunk(scenes, niche, gemini_keys, groq_keys, openai_key, generation_mode=generation_mode)


def _enhance_tags_chunk(
    scenes: List[Dict[str, Any]],
    niche: str,
    gemini_keys: Optional[List[str]] = None,
    groq_keys: Optional[List[str]] = None,
    openai_key: str = "",
    generation_mode: str = "niche"
) -> List[Dict[str, Any]]:
    niche_str = str(niche or "General").strip()
    niche_lower = niche_str.lower()
    is_auto = niche_lower in ("auto", "general", "default", "none", "", "select niche")
    is_voiceover_mode = (str(generation_mode or "").lower() == "voiceover")

    if is_voiceover_mode:
        niche_mandate = """VOICEOVER-BASED VISUAL GENERATION MODE:
The user has configured visual generation to be driven directly by the spoken VOICEOVER SCRIPT CONTENT.
Analyze each sentence's exact spoken topic, literal nouns, verbs, and physical human reality to output matching stock footage queries.
- For example: if the speaker discusses psychology and studying, output research desk, library books, brain science; if the speaker discusses being exhausted or sleeping, output tired person, bedroom clock; if money, output cash and wallet.
- Translate abstract concepts into tangible literal B-roll that exists on Pexels/Pixabay."""
        example_tags = '["person studying desk", "exhausted worker tired", "alarm clock morning"]'
        example_callout = "DISCIPLINE BUILT DAILY"
        example_emp = "focus"
    elif not is_auto:
        if any(k in niche_lower for k in ("space", "sci-fi", "cosmos", "astronomy")):
            niche_mandate = f"""MANDATORY TARGET NICHE: "{niche_str}"
The user has explicitly designated "{niche_str}" as the visual world and aesthetic theme for this entire video.
Regardless of whether the voiceover speaks about psychology, human struggles, motivation, energy, time, money, or philosophy, EVERY SINGLE VISUAL SEARCH TAG MUST BE FIRMLY ROOTED IN THE "Sci-Fi & Space" VISUAL DOMAIN!
- Every search tag MUST depict deep space, galaxies, planets, nebulae, astronauts, telescopes, rockets, cosmic events, space stations, sci-fi landscapes, futuristic cosmos.
- ABSOLUTELY NEVER output modern civilian life, bedrooms, beds, clocks, wallets, cash, children, playgrounds, offices, or parks!
- Translate any abstract narration into a cosmic space visual:
  * 'struggle / stopping you' -> astronaut walking alien planet, spacecraft entering asteroid field
  * 'tired / lack of energy' -> dying red giant star, spacecraft drifting deep void
  * 'money / wealth / resources' -> glowing golden nebula, asteroid belt mining, vast alien city
  * 'science / testing / truth' -> futuristic space observatory, radio telescope array, quantum cosmos research
  * 'happiness / worth living' -> luminous newborn star cluster, sunrise over earth from orbit"""
            example_tags = '["deep space nebula", "astronaut alien surface", "spacecraft asteroid field"]'
            example_callout = "COSMIC EXPANSION"
            example_emp = "cosmos"
        elif any(k in niche_lower for k in ("military", "war", "defense", "conflict")):
            niche_mandate = f"""MANDATORY TARGET NICHE: "{niche_str}"
The user has explicitly designated "{niche_str}" as the visual world for this video.
Regardless of script words, EVERY SINGLE VISUAL SEARCH TAG MUST BE ROOTED IN THE "Military & Defense" DOMAIN!
- Depict armed soldiers, combat vehicles, battle tanks, fighter jets, naval warships, air defense radar, tactical gear, artillery.
- NEVER output boxing, gym, fitness, sports, civilian lifestyle, playgrounds, or bedrooms."""
            example_tags = '["military armed soldiers", "combat battlefield smoke", "fighter jet flight"]'
            example_callout = "DEFENSE SYSTEM READY"
            example_emp = "missile"
        elif any(k in niche_lower for k in ("motivation", "stoic", "discipline", "mindset", "success")):
            niche_mandate = f"""MANDATORY TARGET NICHE: "{niche_str}"
The user has explicitly designated "{niche_str}" as the visual world for this video.
- Depict determined persons climbing mountain peaks, lone runners at dawn/sunrise, intense gym workouts, heavy barbell squats, focused study at desk, high-rise urban skyscrapers, dark moody silhouettes, ancient Roman statues, stormy ocean cliffs.
- ABSOLUTELY NEVER output outer space, galaxies, planets, astronauts, or sci-fi!
- ABSOLUTELY NEVER output domestic kitchens, cooking, makeup, or children toys."""
            example_tags = '["sunrise mountain peak", "runner morning fog", "gym workout athlete"]'
            example_callout = "DISCIPLINE BUILT DAILY"
            example_emp = "discipline"
        elif any(k in niche_lower for k in ("wildlife", "animal", "predator", "ocean")):
            niche_mandate = f"""MANDATORY TARGET NICHE: "{niche_str}"
The user has explicitly designated "{niche_str}" as the visual world for this video.
- Depict wild animals, predators hunting (lions, tigers, eagles, wolves), savannah, deep ocean sharks and whales, lush rainforest.
- NEVER output modern offices, laptops, gym workouts, or domestic houses."""
            example_tags = '["lion pride savannah", "great white shark", "eagle soaring mountain"]'
            example_callout = "APEX PREDATOR"
            example_emp = "hunting"
        elif any(k in niche_lower for k in ("history", "empire", "ancient")):
            niche_mandate = f"""MANDATORY TARGET NICHE: "{niche_str}"
The user has explicitly designated "{niche_str}" as the visual world for this video.
- Depict ancient ruins, pyramids, castles, warriors with swords/armor, temples, pharaohs, Roman colosseums.
- NEVER output modern laptops, smartphones, highways, modern cars, or office cubicles."""
            example_tags = '["ancient roman colosseum", "egyptian pyramids sunset", "medieval stone castle"]'
            example_callout = "ANCIENT EMPIRE"
            example_emp = "history"
        elif any(k in niche_lower for k in ("automotive", "supercar", "racing")):
            niche_mandate = f"""MANDATORY TARGET NICHE: "{niche_str}"
The user has explicitly designated "{niche_str}" as the visual world for this video.
- Depict hypercars, Formula 1 racing, drifting, engine bays, racetracks, night highways.
- NEVER output bedrooms, domestic kitchens, farm animals, or playgrounds."""
            example_tags = '["supercar drifting track", "formula race speed", "engine pistons mechanical"]'
            example_callout = "MAXIMUM VELOCITY"
            example_emp = "speed"
        elif any(k in niche_lower for k in ("finance", "wealth", "business", "luxury")):
            niche_mandate = f"""MANDATORY TARGET NICHE: "{niche_str}"
The user has explicitly designated "{niche_str}" as the visual world for this video.
- Depict stock market tickers, trading floors, cash, gold bullion, modern glass skyscrapers, luxury penthouses, executive meetings.
- NEVER output mud, farms, toys, playgrounds, or messy bedrooms."""
            example_tags = '["stock market ticker", "gold bars vault", "luxury skyscraper office"]'
            example_callout = "FINANCIAL GROWTH"
            example_emp = "wealth"
        elif any(k in niche_lower for k in ("horror", "paranormal")):
            niche_mandate = f"""MANDATORY TARGET NICHE: "{niche_str}"
The user has explicitly designated "{niche_str}" as the visual world for this video.
- Depict eerie fog, haunted houses, dark corridors, full moon, spooky silhouettes, abandoned structures, tombstones.
- NEVER output bright sunny days, cheerful children, beaches, or workout gyms."""
            example_tags = '["eerie abandoned house", "creepy dark woods", "silhouette graveyard mist"]'
            example_callout = "DARK PARANORMAL"
            example_emp = "shadow"
        elif any(k in niche_lower for k in ("crime", "mystery", "noir")):
            niche_mandate = f"""MANDATORY TARGET NICHE: "{niche_str}"
The user has explicitly designated "{niche_str}" as the visual world for this video.
- Depict flashing police sirens, detectives investigating, crime scene tape, prisons, dark rainy alleys, courtroom gavels.
- NEVER output sunny beach parties, weddings, or cheerful cartoons."""
            example_tags = '["police siren night", "detective silhouette crime", "dark rainy alley"]'
            example_callout = "CRIME INVESTIGATION"
            example_emp = "mystery"
        else:
            niche_mandate = f"""MANDATORY TARGET NICHE: "{niche_str}"
Every single search tag must depict the visual world of "{niche_str}". Avoid generic or irrelevant civilian footage."""
            example_tags = '["cinematic 4k footage", "dramatic lighting cinematic", "inspiring landscape aerial"]'
            example_callout = "VISUAL FOCUS"
            example_emp = "focus"
    else:
        niche_mandate = """AUTO-DETECT MODE:
Analyze each sentence to determine the most compelling visual domain.
CRITICAL UNIVERSAL VISUAL RELEVANCE RULES:
1. STRICT DOMAIN FIDELITY: Every search tag MUST physically depict the actual physical reality of the subject matter:
   - Motivation & Stoicism: Output determined persons climbing mountain peaks, lone runners at dawn/sunrise, intense gym workouts, heavy barbell squats, focused study at desk, high-rise urban skyscrapers, dark moody silhouettes. NEVER output outer space, galaxies, planets, astronauts, or sci-fi unless script explicitly mentions astronomy.
   - Military & War: NEVER output boxing, gym, fitness, or civilian sports. Output armed soldiers, combat vehicles, fighter jets, radar, tactical gear.
   - Wildlife & Nature: NEVER output modern offices, laptops, gym workouts, or domestic houses. Output wild animals, predators hunting, savannah, ocean depths, tropical jungle.
   - Space & Astronomy: NEVER output swimming pools, beaches, or kitchens. Output deep space galaxies, planets, nebulae, telescopes, astronauts.
   - History & Ancient Empires: Output ancient ruins, pyramids, castles, warriors, temples, pharaohs.
   - Crime & Mystery: Output police sirens, detectives, crime scene tape, prisons, dark alleys, courtroom.
   - Horror & Paranormal: Output eerie fog, haunted houses, dark corridors, full moon, spooky shadows, cemetery.
   - Science & Medical: Output laboratory beakers, DNA double helix, microscopic cells, hospital surgery, human brain neural network.
   - Automotive & Racing: Output supercars, speed blur, drifting, engines, racetracks, aviation.
   - Finance & Wealth: Output stock charts, trading floors, cash, gold bars, modern skyscrapers, luxury penthouses."""
        example_tags = '["sunrise mountain peak", "runner morning fog", "determined face closeup"]'
        example_callout = "DISCIPLINE BUILT DAILY"
        example_emp = "discipline"

    prompt = f"""You are a master YouTube video editor, B-roll visual director, and motion graphic designer.
{niche_mandate}

Even if sentences are in Urdu, Roman Urdu, Hindi, Arabic, or contain typos/phonetic spelling (e.g. "blastoc misile" -> ballistic missile, "sher shikar" -> tiger/lion hunting, "jang" -> war/battlefield), understand the exact visual context.

UNIVERSAL B-ROLL PRODUCTION STANDARDS:
1. PHYSICAL LITERAL B-ROLL: Translate all metaphors and abstract concepts into tangible physical actions that exist on stock video libraries (Pexels / Pixabay). Never output abstract adjectives or philosophical ideas.
2. SEARCH TAG FORMAT: Strictly 2 to 3 English words per search tag (e.g. "deep space nebula", "military armed soldiers", "runner morning fog").
3. VISUAL DIVERSITY & ZERO REPETITION (MANDATORY):
   - Never repeat the exact same search tags across different scenes in this script.
   - For every sentence, provide varied perspectives and dynamic camera angles (e.g. wide aerial drone, close up tracking, dramatic slow motion, macro detail) so stock libraries deliver distinct, fresh clips.

For EACH sentence provide:
1. "search_tags": 3 to 4 specific, cinematic, highly searchable stock footage queries in ENGLISH (strictly 2 to 3 words each in English). NEVER return non-English words, full sentences, or vague words in search_tags.
2. "callout_text": If this sentence contains a strong claim, key statistic, notable fact, or list-point worth a visual text callout badge, return a concise 3-5 word callout (e.g., "{example_callout}", "93% OF USERS AGREE", "RULE #1: FOCUS FIRST"). Otherwise, return null.
3. "emphasis_word": The single most emphatic, high-impact word in that sentence (numbers, superlatives like "best", "never", "biggest", "critical", or key nouns) for emphasis timing, or null.

Respond ONLY with a STRICT JSON array of objects, one object per sentence in exact order. No markdown code blocks, no commentary.
Example:
[
  {{"search_tags": {example_tags}, "callout_text": "{example_callout}", "emphasis_word": "{example_emp}"}}
]

Sentences:
"""
    for i, s in enumerate(scenes):
        prompt += f"{i+1}. {s['text']}\n"

    content = None
    # Priority 1: Groq high-speed inference (PRIMARY ENGINE)
    if groq_keys:
        clean_groq = [str(k).strip() for k in groq_keys if k and str(k).strip()]
        for gr_key in clean_groq:
            k_mask = f"...{gr_key[-4:]}" if len(gr_key) >= 4 else gr_key
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {gr_key}", "Content-Type": "application/json"}
            # Verified working Groq production models prioritized first:
            for model_id in ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b", "allam-2-7b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
                try:
                    payload = {
                        "model": model_id,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_tokens": 4096
                    }
                    res = requests.post(url, headers=headers, json=payload, timeout=20)
                    if res.status_code == 200:
                        content = res.json()["choices"][0]["message"]["content"]
                        print(f"[SceneAnalyzer] Groq ({model_id} via key {k_mask}) successfully generated visual tags.")
                        break
                    elif res.status_code in (401, 403):
                        print(f"[SceneAnalyzer] Groq key {k_mask} invalid/unauthorized (HTTP {res.status_code}). Failing over to next Groq key...")
                        break
                    elif res.status_code == 429:
                        print(f"[SceneAnalyzer] Groq key {k_mask} rate-limited (HTTP 429). Failing over to next Groq key...")
                        break
                    else:
                        print(f"[SceneAnalyzer] Groq notice ({model_id} via {k_mask}): HTTP {res.status_code}")
                except Exception as e:
                    print(f"[SceneAnalyzer] Groq notice ({model_id} via {k_mask}): {e}")
                    continue
            if content:
                break

    # Priority 2: Google Gemini (FALLBACK ENGINE)
    if not content and gemini_keys:
        content = _call_gemini_api(prompt, gemini_keys)

    # Priority 3: OpenAI
    if not content and openai_key:
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 4096
            }
            res = requests.post(url, headers=headers, json=payload, timeout=20)
            if res.status_code == 200:
                content = res.json()["choices"][0]["message"]["content"]
        except Exception:
            pass

    if not content:
        return []

    try:
        clean_json = re.sub(r'```(?:json)?\s*', '', content)
        clean_json = re.sub(r'```\s*', '', clean_json).strip()
        parsed = None
        try:
            parsed = json.loads(clean_json)
        except Exception:
            # Resilient JSON repair: try auto-closing truncated array
            if clean_json.startswith('[') and not clean_json.endswith(']'):
                last_brace = clean_json.rfind('}')
                if last_brace != -1:
                    try:
                        parsed = json.loads(clean_json[:last_brace+1] + ']')
                    except Exception:
                        pass
            if not parsed:
                # Regex extraction of individual scene JSON objects
                obj_matches = re.findall(r'\{\s*"search_tags"\s*:[^}]+(?:\}[^}]*\}|\})', content)
                parsed = []
                for m in obj_matches:
                    try:
                        obj = json.loads(m)
                        if isinstance(obj, dict):
                            parsed.append(obj)
                    except Exception:
                        continue

        if not isinstance(parsed, list):
            return []

        results = []
        for item in parsed:
            if isinstance(item, list):
                results.append({
                    "search_tags": [str(t).strip() for t in item if t],
                    "callout_text": None,
                    "emphasis_word": None
                })
            elif isinstance(item, dict):
                tags = item.get("search_tags", [])
                if not isinstance(tags, list):
                    tags = []
                callout = item.get("callout_text")
                if callout and isinstance(callout, str):
                    callout = callout.strip()
                    if len(callout.split()) > 7:
                        callout = " ".join(callout.split()[:5])
                else:
                    callout = None

                emp_word = item.get("emphasis_word")
                if emp_word and isinstance(emp_word, str):
                    emp_word = re.sub(r'[^a-zA-Z0-9]', '', emp_word.strip().lower())
                else:
                    emp_word = None

                results.append({
                    "search_tags": [str(t).strip() for t in tags if t],
                    "callout_text": callout,
                    "emphasis_word": emp_word
                })
            else:
                results.append({"search_tags": [], "callout_text": None, "emphasis_word": None})
        return results
    except Exception as e:
        print(f"[SceneAnalyzer] AI response parsing notice: {e}")
        return []


def _apply_callouts_prioritization(scenes: List[Dict[str, Any]]):
    """
    Limits callouts to roughly 1 out of every 4-5 scenes.
    Prioritizes any scene marked is_climax == True, strong statistics/claims,
    and spaces callouts out so they don't appear in adjacent scenes.
    """
    # Initialize all scenes with callout_text = None
    for sc in scenes:
        sc["callout_text"] = None

    if not scenes:
        return

    candidates = []
    for idx, sc in enumerate(scenes):
        raw_text = sc.get("raw_callout_text")
        if raw_text and isinstance(raw_text, str) and raw_text.strip():
            cleaned = raw_text.strip()
            # Calculate priority score
            score = 10
            if sc.get("is_climax"):
                score += 100
            # Boost if contains digits or percentages (stat/fact)
            if re.search(r'\d', cleaned):
                score += 25
            # Boost if contains high-impact markers
            if re.search(r'\b(key|rule|truth|secret|fact|never|always)\b', cleaned, re.IGNORECASE):
                score += 15
            # Prefer 3-5 words
            word_count = len(cleaned.split())
            if 3 <= word_count <= 5:
                score += 10

            candidates.append({
                "index": idx,
                "score": score,
                "text": cleaned
            })

    if not candidates:
        return

    # Max callouts allowed: roughly 1 out of every 4-5 scenes
    max_callouts = max(1, len(scenes) // 4)

    # Sort candidates by score descending
    candidates.sort(key=lambda c: c["score"], reverse=True)

    # Select candidates ensuring minimum distance of 2 scenes between callouts
    selected_indices = []
    for cand in candidates:
        if len(selected_indices) >= max_callouts:
            break
        cand_idx = cand["index"]
        # Check if adjacent to already selected
        if any(abs(cand_idx - s) <= 1 for s in selected_indices):
            continue
        selected_indices.append(cand_idx)

    # If climax was a candidate and didn't get selected due to spacing, force climax
    climax_candidates = [c for c in candidates if scenes[c["index"]].get("is_climax")]
    if climax_candidates:
        climax_idx = climax_candidates[0]["index"]
        if climax_idx not in selected_indices:
            if selected_indices:
                selected_indices.pop()
            selected_indices.append(climax_idx)

    for cand in candidates:
        if cand["index"] in selected_indices:
            scenes[cand["index"]]["callout_text"] = cand["text"]


def _match_emphasis_words_with_timestamps(scenes: List[Dict[str, Any]]):
    """
    Matches LLM-identified emphasis_word with Whisper word-level timestamps.
    Calculates relative timestamps within the scene clip timeline.
    Marks skip_emphasis_zoom = True if within 0.3s of scene boundaries.
    """
    for sc in scenes:
        sc.setdefault("emphasis_word", None)
        sc["emphasis_start"] = None
        sc["emphasis_end"] = None
        sc["emphasis_rel_start"] = None
        sc["emphasis_rel_end"] = None
        sc["skip_emphasis_zoom"] = True

        emp_word = sc.get("emphasis_word")
        words = sc.get("words", [])
        if not emp_word or not words:
            continue

        clean_target = re.sub(r'[^a-zA-Z0-9]', '', str(emp_word)).lower()
        if not clean_target:
            continue

        matched_w = None
        for w in words:
            clean_w = re.sub(r'[^a-zA-Z0-9]', '', str(w.get("word", ""))).lower()
            if clean_w == clean_target:
                matched_w = w
                break

        if matched_w:
            w_start = float(matched_w.get("start", 0))
            w_end = float(matched_w.get("end", 0))
            sc["emphasis_start"] = w_start
            sc["emphasis_end"] = w_end

            rel_start = round(w_start - float(sc.get("start", 0)), 2)
            rel_end = round(w_end - float(sc.get("start", 0)), 2)
            sc["emphasis_rel_start"] = rel_start
            sc["emphasis_rel_end"] = rel_end

            # Boundary conflict check: skip if within 0.3s of scene start or scene end
            dur = float(sc.get("duration", max(0.5, float(sc.get("end", 0)) - float(sc.get("start", 0)))))
            time_from_start = rel_start
            time_from_end = dur - rel_end

            if time_from_start >= 0.3 and time_from_end >= 0.3:
                sc["skip_emphasis_zoom"] = False
            else:
                sc["skip_emphasis_zoom"] = True


def analyze_script_editorial_direction(
    full_transcript_text: str,
    niche: str = "General",
    groq_key: str = "",
    openai_key: str = "",
    groq_keys: Optional[List[str]] = None,
    gemini_keys: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Analyzes the full voiceover transcript with a single LLM call to establish
    overall editorial direction: energy level, pacing multiplier, climax scene, and tone.
    """
    default_editorial = {
        "energy": "medium",
        "pacing_multiplier": 1.0,
        "climax_scene_index": None,
        "tone": "neutral"
    }

    if not full_transcript_text or not full_transcript_text.strip():
        return default_editorial

    # Automatically load API keys from config if not explicitly provided
    if not groq_keys and not groq_key and not openai_key and not gemini_keys:
        try:
            settings = load_settings()
            g_key = settings.get("gemini_api_key", "").strip()
            gemini_keys = settings.get("gemini_api_keys") or ([g_key] if g_key else [])
            groq_keys = settings.get("groq_api_keys") or ([settings.get("groq_api_key")] if settings.get("groq_api_key") else [])
            openai_key = settings.get("openai_api_key", "").strip()
        except Exception:
            gemini_keys = []
            groq_keys = []
            openai_key = ""
    elif groq_key and not groq_keys:
        groq_keys = [groq_key]

    if not gemini_keys and not groq_keys and not openai_key:
        return default_editorial

    # Number sentences for 0-based climax sentence identification
    raw_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', full_transcript_text.strip()) if s.strip()]
    if not raw_sentences:
        raw_sentences = [full_transcript_text.strip()]

    numbered_script = "\n".join(f"[{i}] {s}" for i, s in enumerate(raw_sentences))

    prompt = f"""You are a master video director and pacing editor.
For the niche: "{niche}", analyze the voiceover script below.
Sentences with 0-based indices:
{numbered_script}

Evaluate the script's overall pacing, energy, and climax:
1. "energy": Must be exactly "high", "medium", or "calm".
2. "pacing_multiplier": Float from 0.8 to 1.3 (0.8 = fast-paced rapid cuts/high excitement, 1.0 = standard tempo, 1.3 = slow/calm holds).
3. "climax_scene_index": 0-based integer index of the single most emphatic/important/climactic sentence.
4. "tone": One or two words describing the overall tone (e.g., "inspiring", "urgent", "dark mystery", "educational").

Respond ONLY with a STRICT JSON object in this exact format. No markdown code blocks, no commentary:
{{"energy": "high", "pacing_multiplier": 0.9, "climax_scene_index": 0, "tone": "inspiring"}}
"""

    content = None
    try:
        # Priority 1: Groq high-speed inference (PRIMARY)
        if groq_keys:
            for gr_k in groq_keys:
                clean_k = str(gr_k).strip()
                if not clean_k:
                    continue
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {"Authorization": f"Bearer {clean_k}", "Content-Type": "application/json"}
                for model_id in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]:
                    try:
                        payload = {
                            "model": model_id,
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.3,
                            "max_tokens": 400
                        }
                        res = requests.post(url, headers=headers, json=payload, timeout=20)
                        if res.status_code == 200:
                            content = res.json()["choices"][0]["message"]["content"]
                            break
                        elif res.status_code in (401, 429):
                            break  # Failover to next key in pool
                    except Exception:
                        continue
                if content:
                    break

        # Priority 2: Gemini (FALLBACK)
        if not content and gemini_keys:
            content = _call_gemini_api(prompt, gemini_keys)
        elif not content and openai_key:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            }
            res = requests.post(url, headers=headers, json=payload, timeout=20)
            if res.status_code == 200:
                content = res.json()["choices"][0]["message"]["content"]

        if not content:
            return default_editorial

        clean_json = re.sub(r'```(?:json)?\s*', '', content)
        clean_json = re.sub(r'```\s*', '', clean_json).strip()
        parsed = json.loads(clean_json)
        if not isinstance(parsed, dict):
            return default_editorial

        # Validate energy
        energy = str(parsed.get("energy", "medium")).strip().lower()
        if energy not in ("high", "medium", "calm"):
            energy = "medium"

        # Validate & clamp pacing_multiplier
        try:
            pacing_mult = float(parsed.get("pacing_multiplier", 1.0))
            pacing_mult = max(0.8, min(1.3, round(pacing_mult, 2)))
        except (ValueError, TypeError):
            pacing_mult = 1.0

        # Validate climax_scene_index
        climax_idx = parsed.get("climax_scene_index")
        if climax_idx is not None:
            try:
                climax_idx = int(climax_idx)
                if climax_idx < 0 or climax_idx >= len(raw_sentences):
                    climax_idx = max(0, min(climax_idx, len(raw_sentences) - 1))
            except (ValueError, TypeError):
                climax_idx = None

        tone = str(parsed.get("tone", "neutral")).strip() or "neutral"

        return {
            "energy": energy,
            "pacing_multiplier": pacing_mult,
            "climax_scene_index": climax_idx,
            "tone": tone
        }
    except Exception as e:
        print(f"[SceneAnalyzer] Editorial direction fallback notice: {e}")
        return default_editorial

