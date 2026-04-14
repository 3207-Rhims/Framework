const tableEl = document.getElementById("companyTable");

if (tableEl) {
  const columnsUrl = tableEl.dataset.columnsUrl;
  const rowsUrl = tableEl.dataset.rowsUrl;
  const policyUrl = tableEl.dataset.policyUrl;
  const profileUrl = tableEl.dataset.profileUrl;
  const importUrl = tableEl.dataset.importUrl;
  const clearUrl = tableEl.dataset.clearUrl;
  const sampleUrl = tableEl.dataset.sampleUrl;
  const expertUrlTemplate = tableEl.dataset.expertUrl;
  const submitUrl = tableEl.dataset.submitUrl;
  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

  const defaultWeightConfig = JSON.parse(
    document.getElementById("default-weight-config").textContent
  );
  const weightFormConfig = JSON.parse(
    document.getElementById("weight-form-config").textContent
  );
  const uiText = JSON.parse(document.getElementById("company-ui-text").textContent);

  const cloneValue = (value) => JSON.parse(JSON.stringify(value));

  const fetchJson = async (url, options = {}) => {
    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      credentials: "same-origin",
      ...options,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = data.error || "Request failed";
      throw new Error(message);
    }
    return data;
  };

  const formatWeight = (value) => {
    const rounded = Number(value).toFixed(4);
    return rounded.replace(/0+$/, "").replace(/\.$/, "");
  };

  const buildWeightSummary = (mode, weights, isPending = false) => {
    if (isPending && mode === "custom") {
      return uiText.customWeightsPending;
    }

    const title =
      mode === "custom"
        ? uiText.customWeightsUsed
        : uiText.defaultWeightsUsed;

    const parts = weightFormConfig.map((group) => {
      const values = group.fields
        .map((field) => {
          const value = weights[group.key]?.[field.key];
          return `${field.label}=${formatWeight(value)}`;
        })
        .join(", ");
      return `${group.label}: ${values}`;
    });

    return [title, ...parts].join("<br>");
  };

  const expertModal = document.getElementById("expertModal");
  const expertRowLabel = document.getElementById("expertRowLabel");
  const expertForm = document.getElementById("expertForm");
  let activeRowId = null;
  let activeRowLabel = "";

  const openExpertModal = async (rowData) => {
    activeRowId = rowData.row_id;
    activeRowLabel = rowData.ID || rowData.id || rowData.row_index || activeRowId;
    expertRowLabel.textContent = activeRowLabel;
    expertForm.reset();

    try {
      const url = expertUrlTemplate.replace("/0/", `/${activeRowId}/`);
      const response = await fetchJson(url);
      const feedback = response.feedback || {};
      Object.entries(feedback).forEach(([key, value]) => {
        const field = expertForm.querySelector(`[name="${key}"]`);
        if (!field) return;
        if (field.type === "radio") {
          const radio = expertForm.querySelector(
            `input[name="${key}"][value="${value}"]`
          );
          if (radio) radio.checked = true;
        } else {
          field.value = value || "";
        }
      });
    } catch (error) {
      alert(error.message);
    }

    expertModal.classList.add("show");
  };

  const closeExpertModal = () => {
    expertModal.classList.remove("show");
    activeRowId = null;
  };

  expertModal.addEventListener("click", (event) => {
    if (event.target.classList.contains("modal-backdrop")) {
      closeExpertModal();
    }
  });

  document.querySelectorAll("[data-expert-close]").forEach((btn) => {
    btn.addEventListener("click", closeExpertModal);
  });

  if (expertForm) {
    expertForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!activeRowId) return;
      const data = Object.fromEntries(new FormData(expertForm).entries());
      try {
        const url = expertUrlTemplate.replace("/0/", `/${activeRowId}/`);
        await fetchJson(url, {
          method: "POST",
          body: JSON.stringify(data),
        });
        closeExpertModal();
        alert(uiText.expertFeedbackSaved);
      } catch (error) {
        alert(error.message);
      }
    });
  }

  const weightsModal = document.getElementById("weightsModal");
  const weightsForm = document.getElementById("weightsForm");
  const weightsGroups = document.getElementById("weightsGroups");
  const weightsStatus = document.getElementById("weightsStatus");
  const weightsButton = document.querySelector('[data-action="weights"]');
  const weightsResetButton = document.querySelector("[data-weights-reset]");
  let activeWeightMode = "default";
  let customWeightInputs = cloneValue(defaultWeightConfig);
  let lastUsedWeights = cloneValue(defaultWeightConfig);
  let modalWeightMode = activeWeightMode;

  document.querySelectorAll(".workflow-preview").forEach((preview) => {
    const card = preview.querySelector(".workflow-preview-card");
    if (!card) return;

    const showCard = () => {
      card.hidden = false;
      card.classList.add("is-visible");
      card.setAttribute("aria-hidden", "false");
    };

    const hideCard = () => {
      card.hidden = true;
      card.classList.remove("is-visible");
      card.setAttribute("aria-hidden", "true");
    };

    preview.addEventListener("mouseenter", showCard);
    preview.addEventListener("mouseleave", hideCard);
    preview.addEventListener("focusin", showCard);
    preview.addEventListener("focusout", hideCard);
  });

  const renderWeightGroups = () => {
    weightsGroups.innerHTML = weightFormConfig
      .map((group) => {
        const fields = group.fields
          .map((field) => {
            const value = customWeightInputs[group.key]?.[field.key];
            const defaultValue = group.defaults[field.key];
            return `
              <div class="weight-field">
                <label for="weight-${group.key}-${field.key}">${field.label}</label>
                <input
                  id="weight-${group.key}-${field.key}"
                  name="${group.key}.${field.key}"
                  type="number"
                  min="0"
                  step="0.01"
                  value="${value ?? defaultValue}"
                />
                <span>${uiText.defaultLabel} ${formatWeight(defaultValue)}</span>
              </div>
            `;
          })
          .join("");

        return `
          <section class="weight-group" data-group="${group.key}">
            <h3>${group.label}</h3>
            <p>${group.description}</p>
            <div class="weight-grid">${fields}</div>
          </section>
        `;
      })
      .join("");
  };

  const syncWeightModeUi = (mode = modalWeightMode) => {
    const isCustom = mode === "custom";
    weightsGroups
      .querySelectorAll("input[type='number']")
      .forEach((input) => {
        input.disabled = !isCustom;
      });
    weightsGroups.querySelectorAll(".weight-group").forEach((group) => {
      group.classList.toggle("is-disabled", !isCustom);
    });
  };

  const collectCustomWeights = () => {
    const payload = {};
    weightFormConfig.forEach((group) => {
      payload[group.key] = {};
      group.fields.forEach((field) => {
        const input = weightsForm.querySelector(
          `[name="${group.key}.${field.key}"]`
        );
        payload[group.key][field.key] = input ? input.value.trim() : "";
      });
    });
    return payload;
  };

  const openWeightsModal = () => {
    renderWeightGroups();
    modalWeightMode = activeWeightMode;
    const radio = weightsForm.querySelector(
      `input[name="weight_mode"][value="${modalWeightMode}"]`
    );
    if (radio) radio.checked = true;
    syncWeightModeUi();
    weightsModal.classList.add("show");
  };

  const closeWeightsModal = () => {
    weightsModal.classList.remove("show");
  };

  const updateWeightStatus = (mode, weights, isPending = false) => {
    weightsStatus.innerHTML = buildWeightSummary(mode, weights, isPending);
  };

  weightsModal.addEventListener("click", (event) => {
    if (event.target.classList.contains("modal-backdrop")) {
      closeWeightsModal();
    }
  });

  document.querySelectorAll("[data-weights-close]").forEach((btn) => {
    btn.addEventListener("click", closeWeightsModal);
  });

  if (weightsButton) {
    weightsButton.addEventListener("click", openWeightsModal);
  }

  if (weightsResetButton) {
    weightsResetButton.addEventListener("click", () => {
      modalWeightMode = "default";
      customWeightInputs = cloneValue(defaultWeightConfig);
      renderWeightGroups();
      const radio = weightsForm.querySelector(
        'input[name="weight_mode"][value="default"]'
      );
      if (radio) radio.checked = true;
      syncWeightModeUi("default");
    });
  }

  if (weightsForm) {
    weightsForm.addEventListener("change", (event) => {
      if (event.target.name === "weight_mode") {
        modalWeightMode = event.target.value;
        syncWeightModeUi(modalWeightMode);
      }
    });

    weightsForm.addEventListener("submit", (event) => {
      event.preventDefault();
      activeWeightMode =
        weightsForm.querySelector('input[name="weight_mode"]:checked')?.value ||
        "default";
      modalWeightMode = activeWeightMode;
      customWeightInputs = collectCustomWeights();
      updateWeightStatus(
        activeWeightMode,
        activeWeightMode === "custom" ? customWeightInputs : defaultWeightConfig,
        activeWeightMode === "custom"
      );
      closeWeightsModal();
    });
  }

  updateWeightStatus("default", defaultWeightConfig);

  const initTable = async () => {
    const columnResponse = await fetchJson(columnsUrl);
    const rowResponse = await fetchJson(rowsUrl);

    const feedbackFields = new Set([
      "expert_feedback_cat",
      "expert_feedback_algo",
      "expert_feedback_migration",
    ]);

    const feedbackFormatter = (cell) => {
      const value = cell.getValue();
      if (!value) return "";
      const normalized = String(value).toLowerCase();
      let cls = "feedback-pill";
      if (normalized.includes("appropriate") && !normalized.includes("partially")) {
        cls += " feedback-yes";
      } else if (normalized.includes("partially")) {
        cls += " feedback-partial";
      } else if (normalized.includes("not")) {
        cls += " feedback-no";
      }
      return `<span class="${cls}">${value}</span>`;
    };

    const enhanceColumns = (cols) =>
      cols.map((col) => {
        if (feedbackFields.has(col.field)) {
          return {
            ...col,
            formatter: feedbackFormatter,
            editor: "list",
            editorParams: {
              values: ["Appropriate", "Partially appropriate", "Not appropriate"],
              clearable: true,
            },
            cssClass: "feedback-cell",
          };
        }
        if (col.field === "expert_comments") {
          return {
            ...col,
            formatter: "textarea",
            editor: "textarea",
            cssClass: "feedback-comments",
          };
        }
        return col;
      });

    const deleteColumn = {
      title: " ",
      field: "_delete",
      width: 48,
      hozAlign: "center",
      formatter: "buttonCross",
      cellClick: async (e, cell) => {
        const row = cell.getRow();
        const data = row.getData();
        if (!confirm(uiText.deleteRowConfirm)) return;
        await fetchJson(`${rowsUrl}${data.row_id}/`, { method: "DELETE" });
        row.delete();
      },
    };

    let feedbackColumnVisible = false;
    const feedbackColumn = {
      title: uiText.expertFeedbackColumn,
      field: "_feedback",
      width: 160,
      hozAlign: "center",
      formatter: () => `<button class="btn btn-ghost small">${uiText.expertFeedbackButton}</button>`,
      cellClick: (e, cell) => {
        const row = cell.getRow().getData();
        openExpertModal(row);
      },
    };

    const table = new Tabulator(tableEl, {
      data: rowResponse.rows,
      columns: [deleteColumn, ...enhanceColumns(columnResponse.columns)],
      layout: "fitColumns",
      height: "560px",
      rowHeight: 90,
      variableHeight: true,
      columnDefaults: {
        editor: "textarea",
        formatter: "textarea",
        minWidth: 140,
      },
      index: "row_id",
      cellEdited: async (cell) => {
        const row = cell.getRow().getData();
        const field = cell.getField();
        if (field === "row_index" || field === "_delete") {
          return;
        }
        await fetchJson(`${rowsUrl}${row.row_id}/`, {
          method: "PATCH",
          body: JSON.stringify({ data: { [field]: cell.getValue() } }),
        });
      },
    });

    const searchInput = document.querySelector(".search input");
    searchInput.addEventListener("input", (event) => {
      const value = event.target.value.trim();
      if (!value) {
        table.clearFilter();
        return;
      }
      table.setFilter((data) => {
        return Object.values(data).some((cell) =>
          String(cell).toLowerCase().includes(value.toLowerCase())
        );
      });
    });

    document.querySelector('[data-action="add-row"]').addEventListener("click", async () => {
      const response = await fetchJson(rowsUrl, {
        method: "POST",
        body: JSON.stringify({}),
      });
      table.addRow(response.row);
    });

    const refreshTable = async () => {
      const [columns, rows] = await Promise.all([
        fetchJson(columnsUrl),
        fetchJson(rowsUrl),
      ]);
      const baseCols = [deleteColumn, ...enhanceColumns(columns.columns)];
      table.setColumns(feedbackColumnVisible ? [feedbackColumn, ...baseCols] : baseCols);
      table.setData(rows.rows);
    };

    document.querySelector('[data-action="policy"]').addEventListener("click", async () => {
      try {
        await fetchJson(policyUrl, { method: "POST" });
        await refreshTable();
      } catch (error) {
        alert(error.message);
      }
    });

    document.querySelector('[data-action="profile"]').addEventListener("click", async () => {
      const payload =
        activeWeightMode === "custom"
          ? { weight_mode: "custom", weights: customWeightInputs }
          : { weight_mode: "default" };

      try {
        const result = await fetchJson(profileUrl, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        lastUsedWeights = result.used_weights || cloneValue(defaultWeightConfig);
        updateWeightStatus(result.weight_mode || activeWeightMode, lastUsedWeights);
        await refreshTable();
      } catch (error) {
        alert(error.message);
      }
    });

    const expertButton = document.querySelector('[data-action="expert"]');
    if (expertButton) {
      expertButton.addEventListener("click", async () => {
        feedbackColumnVisible = !feedbackColumnVisible;
        await refreshTable();
        if (feedbackColumnVisible) {
          alert(uiText.expertFeedbackHint);
        }
      });
    }

    const submitButton = document.querySelector('[data-action="submit"]');
    if (submitButton) {
      submitButton.addEventListener("click", async () => {
        if (!confirm(uiText.submitConfirm)) return;
        try {
          const result = await fetchJson(submitUrl, {
            method: "POST",
            body: JSON.stringify({}),
          });
          alert(`${uiText.submittedPrefix} ${result.submission_id}`);
        } catch (error) {
          alert(error.message);
        }
      });
    }

    document.querySelector('[data-action="export"]').addEventListener("click", () => {
      table.download("csv", "company-data.csv");
    });

    document.querySelector('[data-action="clear"]').addEventListener("click", async () => {
      if (!confirm(uiText.clearConfirm)) return;
      try {
        await fetchJson(clearUrl, { method: "POST" });
        table.setColumns([deleteColumn]);
        table.setData([]);
      } catch (error) {
        alert(error.message);
      }
    });

    document.querySelector('[data-action="sample"]').addEventListener("click", async () => {
      if (!confirm(uiText.sampleConfirm)) return;
      try {
        await fetchJson(sampleUrl, { method: "POST" });
        await refreshTable();
      } catch (error) {
        alert(error.message);
      }
    });

    document.querySelector('[data-action="import"]').addEventListener("click", () => {
      const input = document.createElement("input");
      input.type = "file";
      input.accept = ".csv,.xlsx";
      input.addEventListener("change", async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append("file", file);

        const response = await fetch(importUrl, {
          method: "POST",
          headers: {
            "X-CSRFToken": csrfToken,
          },
          body: formData,
          credentials: "same-origin",
        });

        if (!response.ok) {
          const data = await response.json();
          alert(data.error || uiText.importFailed);
          return;
        }

        await response.json();
        await refreshTable();
      });
      input.click();
    });
  };

  initTable().catch((error) => {
    console.error(error);
  });
}
