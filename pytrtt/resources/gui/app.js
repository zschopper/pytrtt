"use strict";

const UI_COPY = [
  ["Setup progress", "Beállítási folyamat"],
  ["Choose a game", "Válassz játékot"],
  ["Select a supported game", "Válassz egy támogatott játékot"],
  ["Find the install", "Találd meg a telepítést"],
  ["Point us to the right files", "Mutasd meg a játékfájlokat"],
  ["Choose an operation", "Válassz műveletet"],
  ["Check, translate, or restore", "Ellenőrzés, fordítás vagy visszaállítás"],
  ["Progress and result", "Folyamat és eredmény"],
  ["Follow the operation", "Kövesd a műveletet"],
  ["Welcome", "Üdvözlünk"],
  ["Welcome to PyTRTT", "Üdvözöl a PyTRTT"],
  ["Version", "Verzió"],
  ["Manage Tomb Raider translations safely in a few clear steps.", "Kezeld biztonságosan a Tomb Raider-fordításokat néhány egyszerű lépésben."],
  ["Tomb Raider translations, made simple", "Tomb Raider-fordítás egyszerűen"],
  ["PyTRTT finds supported Tomb Raider installations, checks their archives, installs available translations, and keeps the data needed to restore the original files.", "A PyTRTT megkeresi a támogatott Tomb Raider-telepítéseket, ellenőrzi az archívumaikat, telepíti az elérhető fordításokat, és megőrzi az eredeti fájlok visszaállításához szükséges adatokat."],
  ["Choose the game and installation, then review the operation before any game file is changed.", "Válaszd ki a játékot és a telepítést, majd nézd át a műveletet, mielőtt bármelyik játékfájl megváltozna."],
  ["Application language", "Alkalmazás nyelve"],
  ["Do not show this welcome page again", "Ne jelenjen meg újra ez az üdvözlőoldal"],
  ["Loading supported games…", "Támogatott játékok betöltése…"],
  ["Searching for installations…", "Telepítések keresése…"],
  ["Search again", "Újrakeresés"],
  ["Choose another folder", "Másik mappa választása"],
  ["Browse for a custom game installation.", "Egyéni játéktelepítés tallózása."],
  ["Custom folder", "Egyéni mappa"],
  ["Validating installation", "Telepítés ellenőrzése"],
  ["Preparing…", "Előkészítés…"],
  ["Translation language", "A fordítás nyelve"],
  ["Hungarian", "Magyar"],
  ["Operation in progress", "Művelet folyamatban"],
  ["Translation credits", "A fordítás közreműködői"],
  ["Contributors", "Közreműködők"],
  ["These people worked on the selected translation.", "A kiválasztott fordításon ők dolgoztak."],
  ["Translators", "Fordítók"], ["Editors", "Szerkesztők"],
  ["Testers", "Tesztelők"], ["Beta testers", "Bétatesztelők"],
  ["Translation tools", "Fordítási eszközök"], ["Communities", "Közösségek"],
  ["Game", "Játék"], ["Installation", "Telepítés"], ["Path", "Elérési út"],
  ["Game status", "Játék állapota"],
  ["Operation", "Művelet"], ["Language", "Nyelv"],
  ["Starting the selected operation safely.", "A kiválasztott művelet biztonságos indítása."],
  ["Completed", "Kész"],
  ["Result", "Eredmény"], ["Total time", "Teljes idő"], ["Recovery data", "Helyreállítási adatok"],
  ["Translate another game", "Másik játék fordítása"],
  ["Launch game", "Játék indítása"],
  ["Exit", "Kilépés"],
  ["Current selection", "Jelenlegi kiválasztás"], ["No game selected", "Nincs kiválasztott játék"],
  ["Back", "Vissza"], ["Get started", "Kezdés"], ["Continue", "Tovább"],
  ["Review", "Áttekintés"], ["Start", "Indítás"],
  ["Find your game files", "Keresd meg a játékfájlokat"],
  ["Choose the game you want to translate, check, or restore.", "Melyik játékot fordítsuk, ellenőrizzük vagy állítsuk vissza?"],
  ["Pick what PyTRTT should do with this install.", "Válaszd ki, mi legyen ezzel a telepítéssel."],
  ["Keep this window open while PyTRTT does its thing.", "Tartsd nyitva az ablakot, amíg a PyTRTT dolgozik."],
  ["Translation package available", "Fordítási csomag elérhető"], ["Not available yet", "Még nem érhető el"],
  ["Ready", "Kész"], ["Translation package unavailable", "Nem érhető el fordítási csomag"],
  ["Selected", "Kiválasztva"],
  ["Installation could not be validated", "A telepítés nem ellenőrizhető"],
  ["No installation was found automatically.", "Nem található automatikusan telepítés."],
  ["Check / dry run", "Ellenőrzés / próbaüzem"],
  ["Install or update translation", "Fordítás telepítése vagy frissítése"],
  ["Restore original files", "Eredeti fájlok helyreállítása"],
  ["Validate without changing files.", "Ellenőrzés a fájlok módosítása nélkül."],
  ["Translation changes are ready to install.", "A fordítás módosításai telepíthetők."],
  ["No safe installation change is currently available.", "Jelenleg nem érhető el biztonságos telepítési módosítás."],
  ["A verified recovery transaction is available.", "Ellenőrzött helyreállítási tranzakció áll rendelkezésre."],
  ["No verified recovery transaction is available.", "Nem áll rendelkezésre ellenőrzött helyreállítási tranzakció."],
  ["Checking the translation package", "A fordítási csomag ellenőrzése"],
  ["Inspecting installed game files", "A telepített játékfájlok vizsgálata"],
  ["Planning required changes", "A szükséges módosítások tervezése"],
  ["Checking current translation resources", "A jelenlegi fordítási erőforrások ellenőrzése"],
  ["Planning resource changes", "Erőforrás-módosítások tervezése"],
  ["Validation complete", "Az ellenőrzés kész"],
  ["Checking translation package", "A fordítási csomag ellenőrzése"],
  ["Inspecting game files", "Játékfájlok vizsgálata"], ["Planning changes", "Módosítások tervezése"],
  ["Installing translation", "Fordítás telepítése"], ["Restoring original files", "Eredeti fájlok helyreállítása"],
  ["Checking recovery data", "Helyreállítási adatok ellenőrzése"],
  ["Reading and verifying the game archives needed for a safe restore.", "A biztonságos visszaállításhoz szükséges játékarchívumok olvasása és ellenőrzése."],
  ["Writing translation resources", "Fordítások írása"],
  ["Writing the prepared translations into safely staged copies of the game archives.", "Az előkészített fordítások írása a játékarchívumok biztonságosan előkészített másolataiba."],
  ["Verifying result", "Eredmény ellenőrzése"], ["Finalizing", "Befejezés"], ["Working", "Feldolgozás"],
  ["Reading and validating the selected translation package.", "A kiválasztott fordítási csomag beolvasása és ellenőrzése."],
  ["Identifying the installed archives and their current state.", "A telepített archívumok és jelenlegi állapotuk azonosítása."],
  ["Comparing installed resources with the expected original and translated states.", "A telepített erőforrások összevetése az elvárt eredeti és fordított állapottal."],
  ["Preparing a safe dry-run plan before any file is modified.", "Biztonságos próbaüzemi terv készítése a fájlok módosítása előtt."],
  ["Building the replacement data and validating archive constraints.", "A csereadatok elkészítése és az archívumkorlátok ellenőrzése."],
  ["Creating recovery data, writing translated resources, and replacing files safely. This can take several minutes.", "Helyreállítási adatok készítése, a fordított erőforrások írása és a fájlok biztonságos cseréje. Ez több percig is eltarthat."],
  ["Putting the original game files back where they belong.", "Visszatesszük az eredeti játékfájlokat a helyükre."],
  ["Checking the files written by the operation.", "A művelet által írt fájlok ellenőrzése."],
  ["The backend operation has completed; preparing the result.", "A háttérművelet befejeződött; az eredmény előkészítése."],
  ["PyTRTT is processing the selected installation.", "A PyTRTT feldolgozza a kiválasztott telepítést."],
  ["Could not complete the operation", "A művelet nem fejezhető be"], ["Details", "Részletek"],
  ["The translation is installed. The game is ready to start.", "A fordítás telepítve van. A játék indítható."],
  ["The check completed successfully. The translation is ready to install.", "Az ellenőrzés sikeresen befejeződött. A fordítás telepíthető."],
  ["The original game files have been restored.", "Az eredeti játékfájlok visszaálltak."],
  ["These game files aren’t in a state PyTRTT recognizes, so we left them untouched.", "A játékfájlok állapota nem ismerős a PyTRTT-nek, ezért nem nyúltunk hozzájuk."],
  ["The operation could not be completed safely. Review the details, then try again.", "A művelet nem fejezhető be biztonságosan. Nézd meg a részleteket, majd próbáld újra."],
  ["The operation is complete.", "A művelet befejeződött."], ["No additional details.", "Nincs további részlet."],
  ["Technical details", "Technikai részletek"], ["Copy details", "Részletek másolása"],
  ["Copied", "Másolva"],
  ["The application bridge is unavailable.", "Az alkalmazáskapcsolat nem érhető el."],
  ["< 1 second", "< 1 másodperc"],
];

let appLanguage = "en";
let targetLanguageChosenByUser = false;

function translatedText(value, language) {
  const exact = UI_COPY.find((pair) => pair[0] === value || pair[1] === value);
  if (exact !== undefined) {
    return exact[language === "hu" ? 1 : 0];
  }
  const patterns = language === "hu"
    ? [
      [/^Step (\d) of 4$/, "$1. lépés / 4"],
      [/^Selected game: (.+)$/, "Kiválasztott játék: $1"],
      [/^(\d+) installation\(s\) found\.$/, "$1 telepítés található."],
      [/^Ready · Version (.+)$/, "Kész · Verzió: $1"],
      [/^Elapsed: (.+)$/, "Eltelt idő: $1"],
      [/^Result: (.+)$/, "Eredmény: $1"],
      [/^Select the (.+) installation you want to manage\.$/, "Válaszd ki a kezelni kívánt $1-telepítést."],
      [/^Game status: (.+)$/, "Játék állapota: $1"],
      [/^Validation failed: (.+)$/, "Az ellenőrzés sikertelen: $1"],
    ]
    : [
      [/^(\d)\. lépés \/ 4$/, "Step $1 of 4"],
      [/^Kiválasztott játék: (.+)$/, "Selected game: $1"],
      [/^(\d+) telepítés található\.$/, "$1 installation(s) found."],
      [/^Kész · Verzió: (.+)$/, "Ready · Version $1"],
      [/^Eltelt idő: (.+)$/, "Elapsed: $1"],
      [/^Eredmény: (.+)$/, "Result: $1"],
      [/^Válaszd ki a kezelni kívánt (.+)-telepítést\.$/, "Select the $1 installation you want to manage."],
      [/^Játék állapota: (.+)$/, "Game status: $1"],
      [/^Az ellenőrzés sikertelen: (.+)$/, "Validation failed: $1"],
    ];
  for (const [pattern, replacement] of patterns) {
    if (pattern.test(value)) {
      return value.replace(pattern, replacement);
    }
  }
  return value;
}

function localizeNode(root) {
  if (root === null) {
    return;
  }
  function localizeTextNode(node) {
    const match = node.nodeValue.match(/^(\s*)(.*?)(\s*)$/s);
    if (match !== null && match[2] !== "") {
      const translated = `${match[1]}${translatedText(match[2], appLanguage)}${match[3]}`;
      if (translated !== node.nodeValue) {
        node.nodeValue = translated;
      }
    }
  }
  if (root.nodeType === Node.TEXT_NODE) {
    localizeTextNode(root);
    return;
  }
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
    localizeTextNode(node);
  }
}

function applyLanguage(language) {
  appLanguage = language;
  document.documentElement.lang = language;
  for (const button of document.querySelectorAll("#app-language [data-language]")) {
    button.setAttribute("aria-pressed", String(button.dataset.language === language));
  }
  document.querySelector(".rail").setAttribute(
    "aria-label",
    translatedText("Setup progress", language),
  );
  localizeNode(document.body);
  for (const indicator of document.querySelectorAll(".selected-indicator")) {
    indicator.textContent = selectedIndicatorText();
  }
  preferMatchingTargetLanguage();
  if (bridge !== null) {
    bridge.setApplicationLanguage(language);
  }
}

function selectedIndicatorText() {
  return translatedText("Selected", appLanguage);
}

function preferMatchingTargetLanguage() {
  if (appLanguage === "en" || targetLanguageChosenByUser) {
    return;
  }
  const target = document.querySelector("#target-language");
  const matching = [...target.options].find((option) => option.value === appLanguage);
  if (matching !== undefined) {
    target.value = matching.value;
  }
}

let selectedGame = null;
let selectedInstallation = null;
let installationChoices = [];
let selectedAction = null;
let bridge = null;
let currentStep = 0;
let operationGeneration = null;
let executionGeneration = null;
let operationStartedAt = null;
let elapsedTimer = null;

function setActiveStep(index) {
  for (const [position, step] of [...document.querySelectorAll(".steps li")].entries()) {
    step.classList.toggle("active", position === index);
    step.classList.toggle("completed", position < index);
  }
}

function selectGame(game, card) {
  selectedGame = game;
  for (const candidate of document.querySelectorAll(".game-card")) {
    const selected = candidate === card;
    candidate.classList.toggle("selected", selected);
    candidate.setAttribute("aria-pressed", String(selected));
    candidate.querySelector(".selected-indicator").hidden = !selected;
  }
  document.querySelector("#summary").textContent = `Selected game: ${game.name}`;
  document.querySelector("#continue").disabled = false;
}

function renderGames(state) {
  applyLanguage(state.locale);
  document.querySelector("#app-version").textContent =
    `${translatedText("Version", appLanguage)} ${state.version}`;
  const container = document.querySelector("#games");
  container.replaceChildren();
  for (const game of state.games) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "game-card";
    card.disabled = !game.available;
    card.setAttribute("aria-pressed", "false");
    const title = document.createElement("strong");
    title.textContent = game.name;
    const status = document.createElement("span");
    status.textContent = game.available ? "Translation package available" : "Not available yet";
    const selected = document.createElement("span");
    selected.className = "selected-indicator";
    selected.textContent = selectedIndicatorText();
    selected.hidden = true;
    card.append(title, status, selected);
    card.addEventListener("click", () => selectGame(game, card));
    card.addEventListener("keydown", (event) => continueFromSelectedCard(event, card));
    container.append(card);
  }
  const skipWelcome = document.querySelector("#skip-welcome");
  skipWelcome.checked = !state.showWelcome;
  if (!state.showWelcome && currentStep === 0) {
    startWizard();
  }
}

function switchPage(from, to, direction) {
  from.classList.remove("active");
  from.classList.toggle("past", direction === "forward");
  from.setAttribute("aria-hidden", "true");
  from.inert = true;
  to.classList.toggle("past", direction === "back");
  // Commit the starting position before activating the destination panel.
  void to.offsetWidth;
  to.classList.remove("past");
  to.classList.add("active");
  to.setAttribute("aria-hidden", "false");
  to.inert = false;
}

function showInstallationStep() {
  if (selectedGame === null) {
    return;
  }
  switchPage(
    document.querySelector("#games"),
    document.querySelector("#installation"),
    "forward",
  );
  document.querySelector("#step-counter").textContent = "Step 2 of 4";
  document.querySelector("#page-title").textContent = "Find your game files";
  document.querySelector("#page-description").textContent =
    `Select the ${selectedGame.name} installation you want to manage.`;
  setActiveStep(1);
  document.querySelector("#summary").textContent = `Selected game: ${selectedGame.name}`;
  document.querySelector("#continue").disabled = true;
  document.querySelector("#back").hidden = false;
  currentStep = 2;
  discoverInstallations();
}

function selectInstallation(installation, card) {
  selectedInstallation = installation;
  for (const candidate of document.querySelectorAll(".installation-card")) {
    const selected = candidate === card;
    candidate.classList.toggle("selected", selected);
    candidate.setAttribute("aria-pressed", String(selected));
    candidate.querySelector(".selected-indicator").hidden = !selected;
  }
  document.querySelector("#summary").textContent =
    `${selectedGame.name} · ${installation.source} · ${installation.path}`;
  document.querySelector("#continue").disabled = false;
}

function continueFromSelectedCard(event, card) {
  if (event.key === "Enter" && card.classList.contains("selected")) {
    event.preventDefault();
    document.querySelector("#continue").click();
  }
}

function installationStatus(installation) {
  if (installation.status === "ready") {
    return installation.build ? `Ready · Version ${installation.build}` : "Ready";
  }
  if (installation.status === "package_unavailable") {
    return "Translation package unavailable";
  }
  return "Installation could not be validated";
}

function renderInstallations(installations, preservePath = null) {
  installationChoices = installations;
  const container = document.querySelector("#installations");
  container.replaceChildren();
  selectedInstallation = null;
  for (const installation of installations) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "installation-card";
    card.disabled = !installation.selectable;
    card.setAttribute("aria-pressed", "false");
    const source = document.createElement("span");
    source.className = "source-badge";
    source.textContent = translatedText(installation.source, appLanguage);
    const path = document.createElement("strong");
    path.textContent = installation.path;
    const status = document.createElement("span");
    status.textContent = installationStatus(installation);
    const selected = document.createElement("span");
    selected.className = "selected-indicator";
    selected.textContent = selectedIndicatorText();
    selected.hidden = true;
    card.append(source, path, status, selected);
    card.addEventListener("click", () => selectInstallation(installation, card));
    card.addEventListener("keydown", (event) => continueFromSelectedCard(event, card));
    container.append(card);
    if (installation.selectable && installation.path === preservePath) {
      selectInstallation(installation, card);
    }
  }
  const selectable = installations.filter((item) => item.selectable);
  if (selectedInstallation === null && selectable.length === 1) {
    const index = installations.indexOf(selectable[0]);
    selectInstallation(selectable[0], container.children[index]);
  }
  document.querySelector("#installation-status").textContent = installations.length === 0
    ? "No installation was found automatically."
    : `${installations.length} installation(s) found.`;
}

function mergeInstallations(installations, customInstallation) {
  return [
    ...installations.filter((item) => item.path !== customInstallation.path),
    customInstallation,
  ];
}

function discoverInstallations() {
  const preserved = selectedInstallation?.path ?? null;
  document.querySelector("#installation-status").textContent = "Searching for installations…";
  document.querySelector("#continue").disabled = true;
  bridge.discoverInstallations(selectedGame.id, (payload) => {
    const result = JSON.parse(payload);
    renderInstallations(result.installations, preserved);
  });
}

function browseInstallation() {
  bridge.browseInstallation(selectedGame.id, (payload) => {
    const result = JSON.parse(payload);
    if (result.installation === null) {
      return;
    }
    renderInstallations(
      mergeInstallations(installationChoices, result.installation),
      result.installation.path,
    );
  });
}

function showGameStep() {
  switchPage(
    document.querySelector("#installation"),
    document.querySelector("#games"),
    "back",
  );
  document.querySelector("#step-counter").textContent = "Step 1 of 4";
  document.querySelector("#page-title").textContent = "Choose a game";
  document.querySelector("#page-description").textContent =
    "Choose the game you want to translate, check, or restore.";
  setActiveStep(0);
  document.querySelector("#back").hidden = true;
  document.querySelector("#summary").textContent = `Selected game: ${selectedGame.name}`;
  document.querySelector("#continue").disabled = false;
  document.querySelector("#continue").innerHTML = "Continue <b>›</b>";
  currentStep = 1;
}

function startWizard() {
  switchPage(
    document.querySelector("#welcome"),
    document.querySelector("#games"),
    "forward",
  );
  document.querySelector("#step-counter").textContent = "Step 1 of 4";
  document.querySelector("#page-title").textContent = "Choose a game";
  document.querySelector("#page-description").textContent =
    "Choose the game you want to translate, check, or restore.";
  setActiveStep(0);
  document.querySelector(".selection-summary").hidden = false;
  document.querySelector("#continue").disabled = selectedGame === null;
  document.querySelector("#continue").innerHTML = "Continue <b>›</b>";
  currentStep = 1;
}

function selectOperation(operation, card) {
  selectedAction = operation.id;
  for (const candidate of document.querySelectorAll(".operation-card")) {
    const selected = candidate === card;
    candidate.classList.toggle("selected", selected);
    candidate.setAttribute("aria-pressed", String(selected));
    candidate.querySelector(".selected-indicator").hidden = !selected;
  }
  document.querySelector("#continue").disabled = false;
  document.querySelector("#continue").textContent = operation.id === "check" ? "Review" : "Start";
  document.querySelector("#language-card").hidden = operation.id !== "install";
  if (operation.id === "install") {
    preferMatchingTargetLanguage();
  }
}

function renderOperations(state) {
  const container = document.querySelector("#operation-cards");
  container.replaceChildren();
  selectedGame.credits = state.credits ?? [];
  selectedAction = null;
  document.querySelector("#language-card").hidden = true;
  const labels = {check: "Check / dry run", install: "Install or update translation", restore: "Restore original files"};
  for (const operation of state.operations ?? []) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "operation-card";
    card.disabled = !operation.available;
    card.setAttribute("aria-pressed", "false");
    const title = document.createElement("strong");
    title.textContent = labels[operation.id];
    const reason = document.createElement("span");
    reason.textContent = operation.reason;
    const selected = document.createElement("span");
    selected.className = "selected-indicator";
    selected.textContent = selectedIndicatorText();
    selected.hidden = true;
    card.append(title, reason, selected);
    card.addEventListener("click", () => selectOperation(operation, card));
    card.addEventListener("keydown", (event) => continueFromSelectedCard(event, card));
    container.append(card);
  }
  document.querySelector("#operation-status").textContent = state.error
    ? `Validation failed: ${state.error}`
    : `${translatedText("Game status", appLanguage)}: ${installationStateLabel(state.status)}`;
  const validationBar = document.querySelector("#validation-bar");
  validationBar.max = 1;
  validationBar.value = 1;
}

function installationStateLabel(status) {
  const labels = {
    en: {
      ready: "Ready to check",
      changes_available: "Translation ready to install",
      already_translated: "Translation already installed",
      unknown_modified: "Unknown file modifications found",
      restored: "Original files restored",
      error: "Could not verify the game",
    },
    hu: {
      ready: "Ellenőrzésre kész",
      changes_available: "A fordítás telepíthető",
      already_translated: "A fordítás már telepítve van",
      unknown_modified: "Ismeretlen fájlmódosításokat találtunk",
      restored: "Az eredeti fájlok helyreállítva",
      error: "A játék nem ellenőrizhető",
    },
  };
  return labels[appLanguage][status] ?? status.replaceAll("_", " ");
}

function progressLabel(message, current, total) {
  const labels = {
    gui_progress_package: "Checking the translation package",
    gui_progress_files: "Inspecting installed game files",
    gui_progress_plan: "Planning required changes",
    gui_progress_detect_resources: "Checking current translation resources",
    gui_progress_plan_resources: "Planning resource changes",
    gui_progress_complete: "Validation complete",
  };
  const label = translatedText(
    labels[message] ?? message.replaceAll("_", " "),
    appLanguage,
  );
  return total > 0 ? `${label} · ${current}/${total}` : label;
}

function showValidationProgress(progress) {
  if (progress.generation !== operationGeneration || currentStep !== 3) {
    return;
  }
  const bar = document.querySelector("#validation-bar");
  if (progress.total > 0) {
    bar.max = progress.total;
    bar.value = Math.min(progress.current, progress.total);
  } else {
    bar.removeAttribute("value");
  }
  document.querySelector("#operation-status").textContent =
    progressLabel(progress.message, progress.current, progress.total);
}

function showOperationStep() {
  switchPage(
    document.querySelector("#installation"),
    document.querySelector("#operations"),
    "forward",
  );
  document.querySelector("#step-counter").textContent = "Step 3 of 4";
  document.querySelector("#page-title").textContent = "Choose an operation";
  document.querySelector("#page-description").textContent =
    "Pick what PyTRTT should do with this install.";
  setActiveStep(2);
  document.querySelector("#operation-status").textContent =
    "Preparing…";
  document.querySelector("#validation-bar").removeAttribute("value");
  document.querySelector("#operation-cards").replaceChildren();
  document.querySelector("#language-card").hidden = true;
  document.querySelector("#continue").disabled = true;
  document.querySelector("#summary").textContent =
    `${selectedGame.name} · ${selectedInstallation.source} · ${selectedInstallation.path}`;
  currentStep = 3;
  bridge.requestOperationState(selectedGame.id, selectedInstallation.path, (generation) => {
    operationGeneration = generation;
  });
}

function back() {
  if (currentStep === 2) {
    showGameStep();
    return;
  }
  if (currentStep === 3) {
    switchPage(
      document.querySelector("#operations"),
      document.querySelector("#installation"),
      "back",
    );
    document.querySelector("#step-counter").textContent = "Step 2 of 4";
    document.querySelector("#page-title").textContent = "Find your game files";
    document.querySelector("#page-description").textContent =
      `Select the ${selectedGame.name} installation you want to manage.`;
    setActiveStep(1);
    document.querySelector("#continue").disabled = selectedInstallation === null;
    document.querySelector("#continue").innerHTML = "Continue <b>›</b>";
    currentStep = 2;
  }
}

function continueWizard() {
  if (currentStep === 0) {
    startWizard();
  } else if (currentStep === 1) {
    showInstallationStep();
  } else if (currentStep === 2 && selectedInstallation !== null) {
    showOperationStep();
  } else if (currentStep === 3 && selectedAction !== null) {
    showProgressStep();
  }
}

function showProgressStep() {
  switchPage(
    document.querySelector("#operations"),
    document.querySelector("#progress"),
    "forward",
  );
  document.querySelector("#step-counter").textContent = "Step 4 of 4";
  document.querySelector("#page-title").textContent = "Progress and result";
  document.querySelector("#page-description").textContent =
    "Keep this window open while PyTRTT does its thing.";
  setActiveStep(3);
  document.querySelector("#back").hidden = true;
  document.querySelector("#continue").disabled = true;
  document.querySelector("#continue").hidden = true;
  document.querySelector(".selection-summary").hidden = true;
  document.querySelector("#progress-title").textContent = "Operation in progress";
  document.querySelector(".progress-copy").hidden = false;
  document.querySelector("#progress-status").textContent = "Preparing…";
  document.querySelector("#progress-detail").textContent =
    "Starting the selected operation safely.";
  document.querySelector("#context-game").textContent = selectedGame.name;
  document.querySelector("#credits-button").hidden = selectedGame.credits.length === 0;
  document.querySelector("#context-installation").textContent = selectedInstallation.source;
  document.querySelector("#context-path").textContent = selectedInstallation.path;
  const operationLabels = {
    check: "Check / dry run",
    install: "Install or update translation",
    restore: "Restore original files",
  };
  document.querySelector("#context-operation").textContent = operationLabels[selectedAction];
  const languageRow = document.querySelector("#context-language-row");
  languageRow.hidden = selectedAction !== "install";
  document.querySelector("#context-language").textContent =
    document.querySelector("#target-language").selectedOptions[0].textContent;
  document.querySelector("#result-detail").hidden = true;
  document.querySelector("#result-summary").hidden = true;
  document.querySelector(".result-actions").hidden = true;
  const bar = document.querySelector("#progress-bar");
  bar.removeAttribute("value");
  operationStartedAt = Date.now();
  updateElapsedTime();
  clearInterval(elapsedTimer);
  elapsedTimer = setInterval(updateElapsedTime, 1000);
  currentStep = 4;
  bridge.executeOperation(
    selectedGame.id,
    selectedInstallation.path,
    selectedAction,
    (generation) => { executionGeneration = generation; },
  );
}

function creditRoleLabel(role) {
  const labels = {
    translators: "Translators",
    editors: "Editors",
    testers: "Testers",
    beta_testers: "Beta testers",
    translation_tools: "Translation tools",
    communities: "Communities",
  };
  const fallback = role.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
  return translatedText(labels[role] ?? fallback, appLanguage);
}

function showTranslationCredits() {
  if (selectedGame === null || selectedGame.credits.length === 0) {
    return;
  }
  document.querySelector("#credits-title").textContent = selectedGame.name;
  document.querySelector("#credits-intro").textContent = translatedText(
    "These people worked on the selected translation.",
    appLanguage,
  );
  const list = document.querySelector("#credits-list");
  list.replaceChildren();
  for (const credit of selectedGame.credits) {
    const row = document.createElement("div");
    const role = document.createElement("dt");
    role.textContent = creditRoleLabel(credit.role);
    const names = document.createElement("dd");
    names.textContent = credit.names.join(", ");
    row.append(role, names);
    list.append(row);
  }
  document.querySelector("#credits-dialog").showModal();
}

function updateElapsedTime() {
  if (operationStartedAt === null) {
    return;
  }
  const seconds = Math.max(0, Math.floor((Date.now() - operationStartedAt) / 1000));
  document.querySelector("#progress-elapsed").textContent =
    `Elapsed: ${formatDuration(seconds)}`;
}

function formatDuration(seconds) {
  if (seconds < 1) {
    return "< 1 second";
  }
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) {
    return `${Math.ceil(bytes / 1024)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function operationProgressCopy(message) {
  const phases = {
    gui_progress_package: ["Checking translation package", "Reading and validating the selected translation package."],
    gui_progress_files: ["Inspecting game files", "Identifying the installed archives and their current state."],
    gui_progress_detect_resources: ["Checking translation resources", "Comparing installed resources with the expected original and translated states."],
    gui_progress_plan: ["Planning changes", "Preparing a safe dry-run plan before any file is modified."],
    gui_progress_plan_resources: ["Planning resource changes", "Building the replacement data and validating archive constraints."],
    gui_progress_install: ["Installing translation", "Creating recovery data, writing translated resources, and replacing files safely. This can take several minutes."],
    gui_progress_install_resources: ["Writing translation resources", "Writing the prepared translations into safely staged copies of the game archives."],
    gui_progress_restore: ["Restoring original files", "Putting the original game files back where they belong."],
    gui_progress_restore_bytes: ["Checking recovery data", "Reading and verifying the game archives needed for a safe restore."],
    gui_progress_verify: ["Verifying result", "Checking the files written by the operation."],
    gui_progress_complete: ["Finalizing", "The backend operation has completed; preparing the result."],
  };
  const copy = phases[message] ?? ["Working", "PyTRTT is processing the selected installation."];
  return copy.map((value) => translatedText(value, appLanguage));
}

function resultStatusLabel(status) {
  const labels = {
    en: {
      already_translated: "Translation installed",
      changes_available: "Translation available",
      restored: "Original files restored",
      unknown_modified: "Unknown modified files",
      error: "Operation failed",
    },
    hu: {
      already_translated: "Fordítás telepítve",
      changes_available: "Fordítás telepíthető",
      restored: "Eredeti fájlok helyreállítva",
      unknown_modified: "Ismeretlen módosított fájlok",
      error: "A művelet sikertelen",
    },
  };
  return labels[appLanguage][status] ?? status.replaceAll("_", " ");
}

function showProgress(progress) {
  if (progress.generation !== executionGeneration || currentStep !== 4) {
    return;
  }
  const bar = document.querySelector("#progress-bar");
  const countable = ["gui_progress_detect_resources", "gui_progress_plan_resources", "gui_progress_install_resources", "gui_progress_restore_bytes"]
    .includes(progress.message);
  if (countable && progress.total > 0) {
    bar.max = progress.total;
    bar.value = progress.current;
  } else {
    bar.removeAttribute("value");
  }
  const copy = operationProgressCopy(progress.message);
  const position = progress.message === "gui_progress_restore_bytes"
    ? `${formatBytes(progress.current)} / ${formatBytes(progress.total)}`
    : `${progress.current}/${progress.total}`;
  document.querySelector("#progress-status").textContent = countable && progress.total > 0
    ? `${position} ${copy[0]} · ${Math.floor(progress.current * 100 / progress.total)}%`
    : copy[0];
  document.querySelector("#progress-detail").textContent = copy[1];
}

function showResult(result) {
  if (result.generation !== executionGeneration || currentStep !== 4) {
    return;
  }
  clearInterval(elapsedTimer);
  elapsedTimer = null;
  updateElapsedTime();
  const success = ["already_translated", "changes_available", "restored"].includes(result.status);
  document.querySelector("#progress-title").textContent = success
    ? "Completed"
    : "Could not complete the operation";
  document.querySelector(".progress-copy").hidden = true;
  const resultMessages = {
    already_translated: "The translation is installed. The game is ready to start.",
    changes_available: "The check completed successfully. The translation is ready to install.",
    restored: "The original game files have been restored.",
    unknown_modified: "These game files aren’t in a state PyTRTT recognizes, so we left them untouched.",
    error: "The operation could not be completed safely. Review the details, then try again.",
  };
  const elapsedSeconds = operationStartedAt === null
    ? 0
    : Math.max(0, Math.floor((Date.now() - operationStartedAt) / 1000));
  document.querySelector("#result-summary").hidden = false;
  document.querySelector("#result-heading").textContent = success
    ? "Ready"
    : "Details";
  document.querySelector("#result-message").textContent =
    resultMessages[result.status] ?? "The operation is complete.";
  document.querySelector("#result-status").textContent = resultStatusLabel(result.status);
  document.querySelector("#result-duration").textContent = formatDuration(elapsedSeconds);
  const recoveryRow = document.querySelector("#result-recovery-row");
  recoveryRow.hidden = !result.recoveryPath;
  const recovery = document.querySelector("#result-recovery");
  recovery.textContent = result.recoveryPath || "—";
  recovery.title = result.recoveryPath || "";
  const detail = document.querySelector("#result-detail");
  const detailPanel = document.querySelector("#result-detail-panel");
  const hasUsefulDetail = Boolean(result.detail) && result.detail !== "0";
  detail.textContent = hasUsefulDetail ? result.detail : "";
  detailPanel.hidden = !hasUsefulDetail;
  detailPanel.open = false;
  document.querySelector(".result-actions").hidden = false;
  document.querySelector("#launch-game").hidden = !success || !selectedInstallation.launchable;
  const bar = document.querySelector("#progress-bar");
  bar.max = 1;
  bar.value = 1;
}

function restartWizard() {
  clearInterval(elapsedTimer);
  elapsedTimer = null;
  operationStartedAt = null;
  executionGeneration = null;
  operationGeneration = null;
  selectedGame = null;
  selectedInstallation = null;
  selectedAction = null;
  document.querySelector("#language-card").hidden = true;
  for (const card of document.querySelectorAll(".game-card")) {
    card.querySelector(".selected-indicator").hidden = true;
    card.classList.remove("selected");
    card.setAttribute("aria-pressed", "false");
  }
  switchPage(
    document.querySelector("#progress"),
    document.querySelector("#games"),
    "back",
  );
  document.querySelector("#step-counter").textContent = "Step 1 of 4";
  document.querySelector("#page-title").textContent = "Choose a game";
  document.querySelector("#page-description").textContent =
    "Choose the game you want to translate, check, or restore.";
  setActiveStep(0);
  document.querySelector("#summary").textContent = "No game selected";
  document.querySelector(".selection-summary").hidden = false;
  document.querySelector("#back").hidden = true;
  const next = document.querySelector("#continue");
  next.hidden = false;
  next.disabled = true;
  next.innerHTML = "Continue <b>›</b>";
  currentStep = 1;
}

document.addEventListener("DOMContentLoaded", () => {
  document.addEventListener("wheel", (event) => {
    if (event.ctrlKey) {
      event.preventDefault();
    }
  }, {passive: false});
  for (const button of document.querySelectorAll("#app-language [data-language]")) {
    button.addEventListener("click", () => applyLanguage(button.dataset.language));
  }
  document.querySelector("#target-language").addEventListener("change", () => {
    targetLanguageChosenByUser = true;
  });
  document.querySelector("#skip-welcome").addEventListener("change", (event) => {
    if (bridge !== null) {
      bridge.setWelcomeEnabled(!event.target.checked);
    }
  });
  new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (mutation.type === "characterData") {
        localizeNode(mutation.target.parentNode);
      } else {
        for (const node of mutation.addedNodes) {
          localizeNode(node);
        }
      }
    }
  }).observe(document.body, {childList: true, characterData: true, subtree: true});
  applyLanguage(appLanguage);
  document.querySelector("#continue").addEventListener("click", continueWizard);
  document.querySelector("#back").addEventListener("click", back);
  document.querySelector("#refresh-installations").addEventListener("click", discoverInstallations);
  document.querySelector("#browse-installation").addEventListener("click", browseInstallation);
  document.querySelector("#restart").addEventListener("click", restartWizard);
  document.querySelector("#launch-game").addEventListener("click", () => {
    bridge.launchGame(selectedGame.id, selectedInstallation.path);
  });
  document.querySelector("#exit-application").addEventListener("click", () => {
    bridge.exitApplication();
  });
  document.querySelector("#credits-button").addEventListener("click", showTranslationCredits);
  document.querySelector("#credits-close").addEventListener("click", () => {
    document.querySelector("#credits-dialog").close();
  });
  document.querySelector("#copy-result-detail").addEventListener("click", (event) => {
    bridge.copyText(document.querySelector("#result-detail").textContent);
    event.target.textContent = "Copied";
    window.setTimeout(() => { event.target.textContent = "Copy details"; }, 1200);
  });
  if (typeof QWebChannel === "undefined" || typeof qt === "undefined") {
    document.querySelector("#games").textContent = "The application bridge is unavailable.";
    return;
  }
  new QWebChannel(qt.webChannelTransport, (channel) => {
    bridge = channel.objects.pytrtt;
    bridge.operationStateReady.connect((payload) => {
      const state = JSON.parse(payload);
      if (state.generation === operationGeneration && currentStep === 3) {
        renderOperations(state);
      }
    });
    bridge.validationProgress.connect((payload) => showValidationProgress(JSON.parse(payload)));
    bridge.operationProgress.connect((payload) => showProgress(JSON.parse(payload)));
    bridge.operationFinished.connect((payload) => showResult(JSON.parse(payload)));
    bridge.initialState((payload) => {
      renderGames(JSON.parse(payload));
      bridge.reportFrontendReady();
    });
  });
});
