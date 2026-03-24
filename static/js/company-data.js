const tableEl = document.getElementById("companyTable");
if (tableEl) {
  const columnsUrl = tableEl.dataset.columnsUrl;
  const rowsUrl = tableEl.dataset.rowsUrl;
  const policyUrl = tableEl.dataset.policyUrl;
  const profileUrl = tableEl.dataset.profileUrl;
  const importUrl = tableEl.dataset.importUrl;
  const clearUrl = tableEl.dataset.clearUrl;
  const utilityUrl = tableEl.dataset.utilityUrl;
  const sampleUrl = tableEl.dataset.sampleUrl;
  const expertUrlTemplate = tableEl.dataset.expertUrl;
  const submitUrl = tableEl.dataset.submitUrl;
  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

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

  const modal = document.getElementById("expertModal");
  const modalRowLabel = document.getElementById("expertRowLabel");
  const expertForm = document.getElementById("expertForm");
  let activeRowId = null;
  let activeRowLabel = "";

  const openExpertModal = async (rowData) => {
    activeRowId = rowData.row_id;
    activeRowLabel = rowData.ID || rowData.id || rowData.row_index || activeRowId;
    modalRowLabel.textContent = activeRowLabel;
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

    modal.classList.add("show");
  };

  const closeExpertModal = () => {
    modal.classList.remove("show");
    activeRowId = null;
  };

  modal.addEventListener("click", (event) => {
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
        alert("Expert feedback saved.");
      } catch (error) {
        alert(error.message);
      }
    });
  }

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
        if (!confirm("Delete this row?")) return;
        await fetchJson(`${rowsUrl}${data.row_id}/`, { method: "DELETE" });
        row.delete();
      },
    };

    let feedbackColumnVisible = false;
    const feedbackColumn = {
      title: "Expert Feedback",
      field: "_feedback",
      width: 160,
      hozAlign: "center",
      formatter: () => "<button class=\"btn btn-ghost small\">Feedback</button>",
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
      try {
        await fetchJson(profileUrl, { method: "POST" });
        await refreshTable();
      } catch (error) {
        alert(error.message);
      }
    });

    // Utility Score button removed

    const expertButton = document.querySelector('[data-action="expert"]');
    if (expertButton) {
      expertButton.addEventListener("click", async () => {
        feedbackColumnVisible = !feedbackColumnVisible;
        await refreshTable();
        if (feedbackColumnVisible) {
          alert("Click the Feedback button on a row to fill the form.");
        }
      });
    }

    const submitButton = document.querySelector('[data-action="submit"]');
    if (submitButton) {
      submitButton.addEventListener("click", async () => {
        if (!confirm("Submit this table? Admins will be able to review it.")) return;
        try {
          const result = await fetchJson(submitUrl, {
            method: "POST",
            body: JSON.stringify({}),
          });
          alert(`Submitted! ID: ${result.submission_id}`);
        } catch (error) {
          alert(error.message);
        }
      });
    }

    document.querySelector('[data-action="export"]').addEventListener("click", () => {
      table.download("csv", "company-data.csv");
    });

    document.querySelector('[data-action="clear"]').addEventListener("click", async () => {
      if (!confirm("Clear all rows and columns? This cannot be undone.")) return;
      try {
        await fetchJson(clearUrl, { method: "POST" });
        table.setColumns([deleteColumn]);
        table.setData([]);
      } catch (error) {
        alert(error.message);
      }
    });

    document.querySelector('[data-action="sample"]').addEventListener("click", async () => {
      if (!confirm("Load sample dataset? This will replace the current table.")) return;
      try {
        await fetchJson(sampleUrl, { method: "POST" });
        await refreshTable();
      } catch (error) {
        alert(error.message);
      }
    });

    // expert handler attached above

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
          alert(data.error || "Import failed.");
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
