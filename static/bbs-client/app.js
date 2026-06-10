const state = {
  studies: [],
  selectedStudy: null,
  selectedSeries: null,
  selectedInstance: null,
  log: [],
  previewUrl: null,
};

const elements = {
  baseUrlInput: document.querySelector("#base-url-input"),
  searchPathInput: document.querySelector("#search-path-input"),
  requestIdInput: document.querySelector("#request-id-input"),
  acceptInput: document.querySelector("#accept-input"),
  loadSamplesButton: document.querySelector("#load-samples-button"),
  clearLogButton: document.querySelector("#clear-log-button"),
  probeOpenApiButton: document.querySelector("#probe-openapi-button"),
  probeHealthButton: document.querySelector("#probe-health-button"),
  connectionBadge: document.querySelector("#connection-badge"),
  workflowBadge: document.querySelector("#workflow-badge"),
  helperMessage: document.querySelector("#helper-message"),
  studiesList: document.querySelector("#studies-list"),
  studiesSummary: document.querySelector("#studies-summary"),
  selectionSummary: document.querySelector("#selection-summary"),
  selectionActions: document.querySelector("#selection-actions"),
  selectionNote: document.querySelector("#selection-note"),
  seriesList: document.querySelector("#series-list"),
  studyJsonButton: document.querySelector("#study-json-button"),
  studyKosButton: document.querySelector("#study-kos-button"),
  studyMultipartButton: document.querySelector("#study-multipart-button"),
  responseSummary: document.querySelector("#response-summary"),
  requestMeta: document.querySelector("#request-meta"),
  headersOutput: document.querySelector("#headers-output"),
  bodyOutput: document.querySelector("#body-output"),
  previewCard: document.querySelector("#preview-card"),
  previewSummary: document.querySelector("#preview-summary"),
  requestLog: document.querySelector("#request-log"),
  logSummary: document.querySelector("#log-summary"),
  studyCardTemplate: document.querySelector("#study-card-template"),
  seriesCardTemplate: document.querySelector("#series-card-template"),
  instanceRowTemplate: document.querySelector("#instance-row-template"),
};

const acceptPresets = {
  fhirJson: "application/fhir+json; fhirVersion=4.0",
  json: "application/dicom+json",
  dicom: "application/dicom",
  multipart: "multipart/related",
  jpeg: "image/jpeg",
};

function baseUrl() {
  return elements.baseUrlInput.value.replace(/\/+$/, "");
}

function currentRequestId() {
  return elements.requestIdInput.value.trim();
}

function makeUrl(path) {
  return new URL(path, `${baseUrl()}/`).toString();
}

function setBadge(element, level, text) {
  element.className = `status-badge ${level}`;
  element.textContent = text;
}

function setConnectionStatus(level, text) {
  setBadge(elements.connectionBadge, level, text);
}

function setWorkflowStatus(level, text) {
  setBadge(elements.workflowBadge, level, text);
}

function setHelperMessage(text, tone = "neutral") {
  elements.helperMessage.className =
    tone === "neutral" ? "helper-message" : `helper-message ${tone}`;
  elements.helperMessage.textContent = text;
}

function readTagValue(entry, tag) {
  if (!entry || !entry[tag] || !entry[tag].Value) {
    return "";
  }

  return entry[tag].Value[0] || "";
}

function extractStudyUid(documentReference) {
  const related =
    documentReference &&
    documentReference.context &&
    Array.isArray(documentReference.context.related)
      ? documentReference.context.related
      : [];
  const match = related.find(
    (item) =>
      item &&
      item.identifier &&
      item.identifier.system === "urn:dicom:uid" &&
      String(item.identifier.value || "").startsWith("urn:oid:")
  );

  if (match) {
    return String(match.identifier.value).replace(/^urn:oid:/, "");
  }

  const attachmentUrl =
    documentReference &&
    Array.isArray(documentReference.content) &&
    documentReference.content[0] &&
    documentReference.content[0].attachment
      ? documentReference.content[0].attachment.url
      : "";
  if (!attachmentUrl) {
    return "";
  }

  const parts = String(attachmentUrl).split("/studies/");
  return parts[1] ? parts[1].split("/")[0] : "";
}

function documentTitle(documentReference) {
  return (
    (documentReference.type && documentReference.type.text) ||
    (Array.isArray(documentReference.content) &&
    documentReference.content[0] &&
    documentReference.content[0].attachment
      ? documentReference.content[0].attachment.title
      : "") ||
    documentReference.id ||
    "Onbekend onderzoek"
  );
}

function modality(documentReference) {
  if (
    documentReference.context &&
    Array.isArray(documentReference.context.event) &&
    documentReference.context.event[0] &&
    Array.isArray(documentReference.context.event[0].coding) &&
    documentReference.context.event[0].coding[0]
  ) {
    return documentReference.context.event[0].coding[0].code || "UNK";
  }

  return "UNK";
}

function groupStudies(bundle) {
  const grouped = new Map();
  const entries = bundle.entry || [];

  for (const entry of entries) {
    const resource = entry.resource;
    if (!resource || resource.resourceType !== "DocumentReference") {
      continue;
    }

    const studyUid = extractStudyUid(resource);
    if (!studyUid) {
      continue;
    }

    const current = grouped.get(studyUid) || {
      studyUid,
      title: documentTitle(resource),
      modality: modality(resource),
      studyDate:
        (resource.context &&
          resource.context.period &&
          resource.context.period.start) ||
        resource.date ||
        "",
      patientDisplay:
        (resource.subject && resource.subject.display) ||
        (resource.subject && resource.subject.reference) ||
        "",
      authors: [],
      documentIds: [],
      documents: [],
    };

    current.documents.push(resource);
    current.documentIds.push(resource.id || "onbekend");
    current.authors.push.apply(
      current.authors,
      (resource.author || []).map((author) => author.display || author.reference)
    );
    grouped.set(studyUid, current);
  }

  return Array.from(grouped.values())
    .map((study) => ({
      ...study,
      authors: Array.from(new Set(study.authors.filter(Boolean))),
      documentIds: Array.from(new Set(study.documentIds.filter(Boolean))),
    }))
    .sort((left, right) =>
      String(right.studyDate).localeCompare(String(left.studyDate))
    );
}

function addLogEntry(entry) {
  state.log.unshift({
    ...entry,
    at: new Date().toLocaleTimeString(),
  });
  state.log = state.log.slice(0, 20);
  renderLog();
}

function responseBodyPreview(kind, payload) {
  if (kind === "json") {
    return JSON.stringify(payload, null, 2);
  }

  if (typeof payload === "string") {
    return payload.slice(0, 7000);
  }

  return `${kind} respons`;
}

function createHeaders(headers) {
  return Object.fromEntries(headers.entries());
}

function explainFailure(record) {
  if (record.status === 406) {
    return "Deze representatie wordt door het endpoint niet geaccepteerd. Controleer de Accept header of gebruik de bijbehorende knop.";
  }

  if (record.status === 404) {
    return "Dit pad of deze UID bestaat niet in de mockdata. Controleer of je nog naar de juiste study, series of instance kijkt.";
  }

  if (
    record.status === 400 &&
    record.path.includes("/9000002/fhir/DocumentReference")
  ) {
    return "De FHIR zoekactie is afgewezen. Dit endpoint verwacht application/fhir+json met fhirVersion=4.0.";
  }

  return `De server reageerde met status ${record.status}. Bekijk rechts de body en headers voor de precieze foutmelding.`;
}

async function request(path, options = {}) {
  const {
    recordRequest = true,
    showInspector = true,
    accept,
    headers: headerInit,
    ...fetchOptions
  } = options;

  const url = makeUrl(path);
  const headers = new Headers(headerInit || {});
  const requestId = currentRequestId();

  if (requestId) {
    headers.set("MedMij-Request-ID", requestId);
  }

  const acceptOverride = elements.acceptInput.value.trim();
  if (accept) {
    headers.set("Accept", accept);
  } else if (acceptOverride) {
    headers.set("Accept", acceptOverride);
  }

  const startedAt = performance.now();

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      headers,
    });

    const durationMs = Math.round(performance.now() - startedAt);
    const contentType = response.headers.get("content-type") || "";
    let payload;
    let preview;
    let kind;

    if (
      contentType.includes("application/json") ||
      contentType.includes("application/dicom+json") ||
      contentType.includes("application/fhir+json")
    ) {
      payload = await response.json();
      preview = responseBodyPreview("json", payload);
      kind = "json";
    } else if (
      contentType.startsWith("image/") ||
      contentType.includes("multipart/related") ||
      contentType.includes("application/dicom")
    ) {
      payload = await response.blob();
      preview = `${payload.size} bytes`;
      kind = "blob";
    } else {
      payload = await response.text();
      preview = responseBodyPreview("text", payload);
      kind = "text";
    }

    const record = {
      url,
      path,
      status: response.status,
      ok: response.ok,
      durationMs,
      contentType,
      headers: createHeaders(response.headers),
      kind,
      payload,
      preview,
    };

    setConnectionStatus("success", `Verbonden met ${baseUrl()}`);

    if (recordRequest) {
      addLogEntry(record);
    }

    if (showInspector) {
      renderInspector(record);
    }

    if (!record.ok) {
      setHelperMessage(explainFailure(record), "warning");
    }

    return record;
  } catch (error) {
    const durationMs = Math.round(performance.now() - startedAt);
    setConnectionStatus("error", `Mock niet bereikbaar op ${baseUrl()}`);
    setWorkflowStatus("error", "Ophalen mislukt");
    setHelperMessage(
      "De frontend kan de mock niet bereiken. Controleer of de mock draait en of de URL hierboven klopt.",
      "error"
    );

    if (recordRequest) {
      addLogEntry({
        url,
        path,
        status: "NET",
        ok: false,
        durationMs,
        contentType: "",
        headers: {},
        kind: "text",
        payload: null,
        preview: error instanceof Error ? error.message : String(error),
      });
    }

    throw error;
  }
}

function renderInspector(record) {
  elements.responseSummary.textContent = `${record.status} • ${
    record.contentType || "onbekend content-type"
  } • ${record.durationMs} ms`;

  const pills = [
    ["Pad", record.path],
    ["Status", String(record.status)],
    ["Content-Type", record.contentType || "n.v.t."],
    ["Duur", `${record.durationMs} ms`],
  ];

  elements.requestMeta.innerHTML = "";
  for (const [label, value] of pills) {
    const pill = document.createElement("div");
    pill.className = "meta-pill";
    pill.innerHTML = `<strong>${escapeHtml(label)}</strong>${escapeHtml(value)}`;
    elements.requestMeta.append(pill);
  }

  elements.headersOutput.textContent = JSON.stringify(record.headers, null, 2);
  elements.bodyOutput.textContent = record.preview || "Geen preview beschikbaar";
  elements.headersOutput.classList.remove("muted");
  elements.bodyOutput.classList.remove("muted");
}

function revokePreview() {
  if (state.previewUrl) {
    URL.revokeObjectURL(state.previewUrl);
    state.previewUrl = null;
  }
}

function renderPreview(info = null) {
  revokePreview();

  if (!info) {
    elements.previewSummary.textContent = "Nog geen preview geladen";
    elements.previewCard.className = "preview-card empty-state";
    elements.previewCard.innerHTML =
      'Kies een instance en klik op <strong>JPEG preview</strong>.';
    return;
  }

  elements.previewSummary.textContent = info.instanceUid;
  elements.previewCard.className = "preview-card";
  elements.previewCard.innerHTML = "";

  const image = document.createElement("img");
  state.previewUrl = URL.createObjectURL(info.blob);
  image.src = state.previewUrl;
  image.alt = `JPEG preview voor ${info.instanceUid}`;

  const wrapper = document.createElement("div");
  wrapper.className = "preview-meta";

  if (info.numberOfFrames > 1) {
    const sliderWrapper = document.createElement("div");
    sliderWrapper.className = "frame-slider";

    const currentFrame = info.currentFrame || 1;
    const label = document.createElement("label");
    label.setAttribute("for", "frame-slider-input");
    label.textContent = `Frame ${currentFrame} / ${info.numberOfFrames}`;

    const slider = document.createElement("input");
    slider.id = "frame-slider-input";
    slider.type = "range";
    slider.min = "1";
    slider.max = String(info.numberOfFrames);
    slider.value = String(currentFrame);
    let debounceTimer = null;
    slider.addEventListener("input", () => {
      label.textContent = `Frame ${slider.value} / ${info.numberOfFrames}`;
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        void loadFrame(info, parseInt(slider.value, 10), image, label);
      }, 0);
    });

    sliderWrapper.append(label, slider);
    wrapper.append(sliderWrapper);
  }

  const details = document.createElement("div");
  details.innerHTML = `
    <p><strong>Study UID:</strong> ${escapeHtml(info.studyUid)}</p>
    <p><strong>Series UID:</strong> ${escapeHtml(info.seriesUid)}</p>
    <p><strong>Instance UID:</strong> ${escapeHtml(info.instanceUid)}</p>
    <p><strong>Bestandsgrootte:</strong> ${escapeHtml(String(info.blob.size))} bytes</p>
  `;

  const actions = document.createElement("div");
  actions.className = "quick-actions";

  const openButton = document.createElement("button");
  openButton.className = "secondary small";
  openButton.textContent = "Open afbeelding";
  openButton.addEventListener("click", () => {
    window.open(state.previewUrl, "_blank");
  });

  actions.append(openButton);
  wrapper.append(details, actions);
  elements.previewCard.append(image, wrapper);
}

async function loadFrame(info, frameId, imageElement, labelElement) {
  const record = await request(
    `/9000002/wado/studies/${encodeURIComponent(
      info.studyUid
    )}/series/${encodeURIComponent(
      info.seriesUid
    )}/instances/${encodeURIComponent(info.instanceUid)}/frames/${frameId}/rendered`,
    { accept: acceptPresets.jpeg, recordRequest: false, showInspector: false }
  );

  if (record.ok) {
    revokePreview();
    state.previewUrl = URL.createObjectURL(record.payload);
    imageElement.src = state.previewUrl;
    labelElement.textContent = `Frame ${frameId} / ${info.numberOfFrames}`;
  }
}

function appendDetail(container, label, value) {
  const dt = document.createElement("dt");
  dt.textContent = label;
  const dd = document.createElement("dd");
  dd.textContent = value;
  container.append(dt, dd);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderStudies() {
  elements.studiesList.innerHTML = "";

  if (!state.studies.length) {
    elements.studiesSummary.textContent = "Nog geen onderzoeken geladen";
    elements.studiesList.className = "list empty-state";
    elements.studiesList.innerHTML =
      "Nog geen onderzoeken zichtbaar. Het scherm verwacht een werkende mock en haalt daarna de standaard beeldbeschikbaarheid DocumentReference-resultaten op.";
    return;
  }

  elements.studiesSummary.textContent = `${state.studies.length} onderzoek${
    state.studies.length === 1 ? "" : "en"
  } gevonden`;
  elements.studiesList.className = "list";

  for (const study of state.studies) {
    const fragment = elements.studyCardTemplate.content.cloneNode(true);
    const card = fragment.querySelector(".study-card");

    if (state.selectedStudy && study.studyUid === state.selectedStudy.studyUid) {
      card.classList.add("active");
    }

    fragment.querySelector(".study-badge").textContent = study.modality;
    fragment.querySelector(".study-title").textContent = study.title;
    fragment.querySelector(".study-meta").textContent =
      `${study.documents.length} DocumentReference item(s) • ${study.patientDisplay || "Onbekende patiënt"}`;

    const details = fragment.querySelector(".study-details");
    appendDetail(details, "Study UID", study.studyUid);
    appendDetail(details, "Datum", study.studyDate || "n.v.t.");
    appendDetail(details, "Documenten", study.documentIds.join(", "));
    appendDetail(details, "Auteurs", study.authors.join(", ") || "n.v.t.");

    fragment
      .querySelector(".study-select-button")
      .addEventListener("click", () => selectStudy(study));

    elements.studiesList.append(fragment);
  }
}

function renderSeries() {
  elements.seriesList.innerHTML = "";

  if (!state.selectedStudy) {
    elements.selectionSummary.textContent = "Nog geen onderzoek geselecteerd";
    elements.selectionActions.hidden = true;
    elements.selectionNote.textContent =
      "Selecteer links een onderzoek. Daarna worden de series en beelden automatisch opgehaald.";
    elements.seriesList.className = "series-list empty-state";
    elements.seriesList.textContent = "Nog geen onderzoek geselecteerd.";
    return;
  }

  elements.selectionActions.hidden = false;
  elements.selectionNote.textContent =
    "Gebruik de study-knoppen om JSON metadata, KOS manifest of de volledige multipart study-respons te bekijken.";

  if (!state.selectedStudy.seriesEntries) {
    elements.selectionSummary.textContent = `${state.selectedStudy.studyUid}`;
    elements.seriesList.className = "series-list empty-state";
    elements.seriesList.textContent =
      "Series en instances van het geselecteerde onderzoek worden opgehaald.";
    return;
  }

  elements.selectionSummary.textContent = `${state.selectedStudy.seriesEntries.length} series voor geselecteerd onderzoek`;
  elements.seriesList.className = "series-list";

  for (const series of state.selectedStudy.seriesEntries) {
    const fragment = elements.seriesCardTemplate.content.cloneNode(true);
    const card = fragment.querySelector(".series-card");

    if (state.selectedSeries && series.seriesUid === state.selectedSeries.seriesUid) {
      card.classList.add("active");
    }

    fragment.querySelector(".series-label").textContent =
      series.modality || state.selectedStudy.modality || "SERIES";
    fragment.querySelector(".series-title").textContent =
      series.description || series.seriesUid;
    fragment.querySelector(".series-meta").textContent =
      `${(series.instances && series.instances.length) || 0} instance(s) • ${
        series.studyDescription || state.selectedStudy.title
      }`;

    fragment
      .querySelector(".series-json-button")
      .addEventListener("click", () => fetchSeriesMetadata(series));
    fragment
      .querySelector(".series-multipart-button")
      .addEventListener("click", () => fetchSeriesMultipart(series));

    const instanceList = fragment.querySelector(".instance-list");
    if (!series.instances || !series.instances.length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "Voor deze series zijn nog geen instances ingelezen.";
      instanceList.append(empty);
    } else {
      for (const instance of series.instances) {
        const rowFragment = elements.instanceRowTemplate.content.cloneNode(true);
        rowFragment.querySelector(".instance-title").textContent =
          instance.instanceUid;
        rowFragment.querySelector(".instance-meta").textContent = `${
          instance.sopClassUid || "Onbekende SOP Class"
        } • ${
          instance.numberOfFrames > 1
            ? `${instance.numberOfFrames} frames`
            : "single frame"
        }`;

        rowFragment
          .querySelector(".instance-dicom-button")
          .addEventListener("click", () => fetchInstanceDicom(series, instance));
        rowFragment
          .querySelector(".instance-preview-button")
          .addEventListener("click", () => fetchRenderedPreview(series, instance));

        instanceList.append(rowFragment);
      }
    }

    elements.seriesList.append(fragment);
  }
}

function renderLog() {
  elements.requestLog.innerHTML = "";
  elements.logSummary.textContent = `${state.log.length} actie${
    state.log.length === 1 ? "" : "s"
  }`;

  if (!state.log.length) {
    elements.requestLog.className = "log-list empty-state";
    elements.requestLog.textContent = "Nog geen testacties uitgevoerd.";
    return;
  }

  elements.requestLog.className = "log-list";
  for (const entry of state.log) {
    const item = document.createElement("article");
    item.className = "log-item";
    item.innerHTML = `
      <div class="log-item-top">
        <strong>${escapeHtml(entry.path)}</strong>
        <span class="log-status ${entry.ok ? "ok" : "error"}">${escapeHtml(
      String(entry.status)
    )}</span>
      </div>
      <div class="log-meta">${escapeHtml(entry.at)} • ${escapeHtml(
      entry.contentType || "geen content-type"
    )} • ${escapeHtml(String(entry.durationMs))} ms</div>
    `;
    elements.requestLog.append(item);
  }
}

function seriesFromManifestEntry(entry) {
  return {
    studyUid: readTagValue(entry, "0020000D"),
    seriesUid: readTagValue(entry, "0020000E"),
    modality: readTagValue(entry, "00080060"),
    studyDescription: readTagValue(entry, "00081030"),
    description: readTagValue(entry, "0008103E"),
    url: readTagValue(entry, "00081190"),
    instances: [],
  };
}

function instanceFromMetadataEntry(entry) {
  const numberOfFramesValue =
    entry["00280008"] && entry["00280008"].Value
      ? parseInt(entry["00280008"].Value[0], 10)
      : 1;
  return {
    studyUid: readTagValue(entry, "0020000D"),
    seriesUid: readTagValue(entry, "0020000E"),
    instanceUid: readTagValue(entry, "00080018"),
    sopClassUid: readTagValue(entry, "00080016"),
    modality: readTagValue(entry, "00080060"),
    studyDescription: readTagValue(entry, "00081030"),
    seriesDescription: readTagValue(entry, "0008103E"),
    bodyPartExamined: readTagValue(entry, "00180015"),
    numberOfFrames: numberOfFramesValue > 1 ? numberOfFramesValue : 1,
  };
}

async function verifyConnection(options = {}) {
  try {
    const record = await request("/health", {
      accept: "application/json",
      recordRequest:
        options.recordRequest !== undefined ? options.recordRequest : false,
      showInspector:
        options.showInspector !== undefined ? options.showInspector : false,
    });

    if (!record.ok) {
      throw new Error("Health endpoint gaf geen succesvolle respons");
    }

    setConnectionStatus("success", `Verbonden met ${baseUrl()}`);
    return true;
  } catch (error) {
    return false;
  }
}

async function loadSamples(options = {}) {
  setWorkflowStatus("pending", "FHIR beeldonderzoeken laden");
  setHelperMessage(
    "De frontend haalt nu de standaard beeldbeschikbaarheid DocumentReference-resultaten op.",
    "neutral"
  );

  try {
    const record = await request(elements.searchPathInput.value.trim(), {
      accept: acceptPresets.fhirJson,
      recordRequest:
        options.recordRequest !== undefined ? options.recordRequest : true,
      showInspector:
        options.showInspector !== undefined ? options.showInspector : true,
    });

    if (!record.ok) {
      throw new Error(record.preview || "FHIR zoekactie mislukt");
    }

    state.studies = groupStudies(record.payload);
    state.selectedStudy = null;
    state.selectedSeries = null;
    state.selectedInstance = null;
    renderPreview();
    renderStudies();
    renderSeries();

    if (!state.studies.length) {
      setWorkflowStatus("warning", "Geen onderzoeken gevonden");
      setHelperMessage(
        "De zoekactie gaf geen DocumentReference-resultaten terug. Controleer het zoekpad of de mockdata.",
        "warning"
      );
      return;
    }

    setWorkflowStatus(
      "success",
      `${state.studies.length} onderzoek${
        state.studies.length === 1 ? "" : "en"
      } geladen`
    );
    setHelperMessage(
      "De onderzoeken links komen uit de beeldbeschikbaarheid zoekactie. Het eerste onderzoek wordt automatisch geopend zodat je direct series en beelden ziet.",
      "neutral"
    );

    if (options.autoSelectFirst !== false) {
      await selectStudy(state.studies[0], {
        recordRequest: false,
        showInspector: false,
      });
    }
  } catch (error) {
    setWorkflowStatus("error", "Voorbeelddata laden mislukt");
    if (!(error instanceof Error)) {
      throw error;
    }
  }
}

async function selectStudy(study, options = {}) {
  state.selectedStudy = {
    ...study,
    seriesEntries: null,
  };
  state.selectedSeries = null;
  state.selectedInstance = null;
  renderStudies();
  renderSeries();
  renderPreview();

  setWorkflowStatus("pending", "Series en instances laden");
  setHelperMessage(
    `Onderzoek geselecteerd. We halen nu de study manifest- en series metadata op voor ${study.studyUid}.`,
    "neutral"
  );

  try {
    const manifestRecord = await request(
      `/9000002/wado/studies/${encodeURIComponent(study.studyUid)}/series`,
      {
        accept: acceptPresets.json,
        recordRequest:
          options.recordRequest !== undefined ? options.recordRequest : true,
        showInspector:
          options.showInspector !== undefined ? options.showInspector : true,
      }
    );

    if (!manifestRecord.ok) {
      throw new Error(
        manifestRecord.preview || "Series manifest kon niet worden opgehaald"
      );
    }

    const seriesEntries = manifestRecord.payload.map(seriesFromManifestEntry);
    state.selectedStudy.seriesEntries = seriesEntries;

    await Promise.all(
      seriesEntries.map((series) =>
        hydrateSeries(study, series, {
          recordRequest: false,
          showInspector: false,
        })
      )
    );

    setWorkflowStatus(
      "success",
      `${seriesEntries.length} series geladen`
    );
    setHelperMessage(
      "Gebruik nu de study-knoppen bovenin of vraag per instance een DICOM-bestand of JPEG preview op.",
      "neutral"
    );
    renderSeries();
  } catch (error) {
    setWorkflowStatus("error", "Series laden mislukt");
    if (!(error instanceof Error)) {
      throw error;
    }
  }
}

async function hydrateSeries(study, series, options = {}) {
  const record = await request(
    `/9000002/wado/studies/${encodeURIComponent(
      study.studyUid
    )}/series/${encodeURIComponent(series.seriesUid)}/metadata`,
    {
      accept: acceptPresets.json,
      recordRequest:
        options.recordRequest !== undefined ? options.recordRequest : false,
      showInspector:
        options.showInspector !== undefined ? options.showInspector : false,
    }
  );

  if (!record.ok) {
    throw new Error(record.preview || "Series metadata kon niet worden opgehaald");
  }

  series.instances = record.payload.map(instanceFromMetadataEntry);
}

async function fetchStudyJson() {
  if (!state.selectedStudy) {
    return;
  }

  try {
    const record = await request(
      `/9000002/wado/studies/${encodeURIComponent(
        state.selectedStudy.studyUid
      )}/metadata`,
      { accept: acceptPresets.json }
    );

    if (record.ok) {
      setHelperMessage(
        "Je kijkt nu naar study metadata in DICOM JSON. Hiermee controleer je welke instances voor dit onderzoek beschikbaar zijn.",
        "neutral"
      );
    }
  } catch (error) {
    showError(error);
  }
}

async function fetchStudyKos() {
  if (!state.selectedStudy) {
    return;
  }

  try {
    const record = await request(
      `/9000002/wado/studies/${encodeURIComponent(
        state.selectedStudy.studyUid
      )}/metadata`,
      { accept: acceptPresets.dicom }
    );

    if (record.ok) {
      elements.bodyOutput.textContent =
        `${record.preview}\n\nBinary KOS manifest ontvangen. Gebruik vooral de headers en content-type om te controleren of de study als DICOM-bestand wordt aangeboden.`;
      setHelperMessage(
        "Je kijkt nu naar het KOS manifest op studyniveau. Dit is de DICOM-variant van de study metadata.",
        "neutral"
      );
    }
  } catch (error) {
    showError(error);
  }
}

async function fetchStudyMultipart() {
  if (!state.selectedStudy) {
    return;
  }

  try {
    const record = await request(
      `/9000002/wado/studies/${encodeURIComponent(state.selectedStudy.studyUid)}`,
      { accept: acceptPresets.multipart }
    );

    if (record.ok) {
      elements.bodyOutput.textContent =
        `${record.preview}\n\nMultipart DICOM payload ontvangen. Controleer in de headers vooral de boundary en het multipart content-type.`;
      setHelperMessage(
        "Je kijkt nu naar de volledige study-respons als multipart DICOM.",
        "neutral"
      );
    }
  } catch (error) {
    showError(error);
  }
}

async function fetchSeriesMetadata(series) {
  state.selectedSeries = series;
  renderSeries();

  try {
    const record = await request(
      `/9000002/wado/studies/${encodeURIComponent(
        state.selectedStudy.studyUid
      )}/series/${encodeURIComponent(series.seriesUid)}/instances`,
      { accept: acceptPresets.json }
    );

    if (record.ok) {
      setHelperMessage(
        "Je kijkt nu naar de metadata van alle instances in deze series.",
        "neutral"
      );
    }
  } catch (error) {
    showError(error);
  }
}

async function fetchSeriesMultipart(series) {
  state.selectedSeries = series;
  renderSeries();

  try {
    const record = await request(
      `/9000002/wado/studies/${encodeURIComponent(
        state.selectedStudy.studyUid
      )}/series/${encodeURIComponent(series.seriesUid)}`,
      { accept: acceptPresets.multipart }
    );

    if (record.ok) {
      elements.bodyOutput.textContent =
        `${record.preview}\n\nMultipart DICOM payload voor de geselecteerde series ontvangen.`;
      setHelperMessage(
        "Je kijkt nu naar de volledige DICOM multipart-respons voor deze series.",
        "neutral"
      );
    }
  } catch (error) {
    showError(error);
  }
}

async function fetchInstanceDicom(series, instance) {
  state.selectedSeries = series;
  state.selectedInstance = instance;
  renderSeries();

  try {
    const record = await request(
      `/9000002/wado/studies/${encodeURIComponent(
        state.selectedStudy.studyUid
      )}/series/${encodeURIComponent(
        series.seriesUid
      )}/instances/${encodeURIComponent(instance.instanceUid)}`,
      { accept: acceptPresets.dicom }
    );

    if (record.ok) {
      elements.bodyOutput.textContent =
        `${record.preview}\n\nBinary DICOM instance ontvangen.`;
      setHelperMessage(
        "Je kijkt nu naar de ruwe DICOM instance voor het geselecteerde beeld.",
        "neutral"
      );
    }
  } catch (error) {
    showError(error);
  }
}

async function fetchRenderedPreview(series, instance) {
  state.selectedSeries = series;
  state.selectedInstance = instance;
  renderSeries();

  try {
    const record = await request(
      `/9000002/wado/studies/${encodeURIComponent(
        state.selectedStudy.studyUid
      )}/series/${encodeURIComponent(
        series.seriesUid
      )}/instances/${encodeURIComponent(instance.instanceUid)}/rendered`,
      { accept: acceptPresets.jpeg }
    );

    if (!record.ok) {
      throw new Error(record.preview || "JPEG preview kon niet worden opgehaald");
    }

    renderPreview({
      blob: record.payload,
      studyUid: state.selectedStudy.studyUid,
      seriesUid: series.seriesUid,
      instanceUid: instance.instanceUid,
      numberOfFrames: instance.numberOfFrames,
      currentFrame: 1,
    });
    setHelperMessage(
      "Je kijkt nu naar de gerenderde JPEG-preview van de geselecteerde DICOM instance.",
      "neutral"
    );
  } catch (error) {
    showError(error);
  }
}

async function probe(path) {
  try {
    await request(path, { accept: "application/json" });
  } catch (error) {
    showError(error);
  }
}

function showError(error) {
  const message = error instanceof Error ? error.message : String(error);
  elements.responseSummary.textContent = "Actie mislukt";
  elements.requestMeta.innerHTML = "";
  elements.headersOutput.textContent = "Geen response headers";
  elements.bodyOutput.textContent = message;
  elements.headersOutput.classList.add("muted");
  elements.bodyOutput.classList.remove("muted");
}

function clearLog() {
  state.log = [];
  renderLog();
}

function handleBaseUrlChange() {
  setConnectionStatus("pending", "URL gewijzigd, controleer opnieuw");
  setWorkflowStatus("pending", "Huidige data hoort mogelijk bij oude URL");
  setHelperMessage(
    "De mock URL is aangepast. Klik op Voorbeelddata opnieuw laden om opnieuw te verbinden en de studies opnieuw op te halen.",
    "warning"
  );
}

async function startup() {
  setConnectionStatus("pending", "Verbinding controleren");
  setWorkflowStatus("pending", "Voorbeelddata laden");
  setHelperMessage(
    "Dit scherm controleert eerst of de mock bereikbaar is en haalt daarna automatisch de standaard beeldstudies op.",
    "neutral"
  );

  const connected = await verifyConnection({
    recordRequest: false,
    showInspector: false,
  });

  if (!connected) {
    renderStudies();
    renderSeries();
    renderPreview();
    renderLog();
    return;
  }

  await loadSamples({
    autoSelectFirst: true,
    recordRequest: false,
    showInspector: false,
  });
}

function bindEvents() {
  elements.loadSamplesButton.addEventListener("click", () =>
    loadSamples({
      autoSelectFirst: true,
      recordRequest: true,
      showInspector: true,
    })
  );
  elements.clearLogButton.addEventListener("click", clearLog);
  elements.probeOpenApiButton.addEventListener("click", () => probe("/openapi.json"));
  elements.probeHealthButton.addEventListener("click", () =>
    verifyConnection({ recordRequest: true, showInspector: true })
  );
  elements.studyJsonButton.addEventListener("click", fetchStudyJson);
  elements.studyKosButton.addEventListener("click", fetchStudyKos);
  elements.studyMultipartButton.addEventListener("click", fetchStudyMultipart);
  elements.baseUrlInput.addEventListener("change", handleBaseUrlChange);
}

function init() {
  bindEvents();
  renderStudies();
  renderSeries();
  renderPreview();
  renderLog();
  void startup();
}

init();
