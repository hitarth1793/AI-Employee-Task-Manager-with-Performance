document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("authorized-action-form");
    const typeInput = document.getElementById("authorized-action-type");
    const taskFields = document.getElementById("action-task-fields");
    const leaveFields = document.getElementById("action-leave-fields");
    const approvalFields = document.getElementById("action-approval-fields");
    const proposal = document.getElementById("authorized-action-proposal");
    const controls = document.getElementById("authorized-action-controls");
    const message = document.getElementById("authorized-action-message");
    const confirmButton = document.getElementById("confirm-authorized-action");
    const cancelButton = document.getElementById("cancel-authorized-action");
    if (!form) return;

    let actionId = null;

    function updateFields() {
        const actionType = typeInput.value;
        taskFields.hidden = actionType !== "CREATE_TASK";
        leaveFields.hidden = actionType !== "REQUEST_LEAVE";
        approvalFields.hidden = actionType !== "APPROVE_LEAVE";
    }

    async function sendAction(url) {
        const csrf = form.querySelector("[name=csrfmiddlewaretoken]").value;
        const response = await fetch(url, {
            method: "POST",
            headers: {"X-CSRFToken": csrf},
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "The action could not be completed.");
        return result;
    }

    typeInput.addEventListener("change", updateFields);
    updateFields();

    form.addEventListener("submit", async event => {
        event.preventDefault();
        message.textContent = "";
        try {
            const response = await fetch("/assistant/actions/propose/", {
                method: "POST",
                headers: {"X-CSRFToken": form.querySelector("[name=csrfmiddlewaretoken]").value},
                body: new FormData(form),
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || "The proposal could not be created.");
            actionId = result.action_id;
            proposal.textContent = `${result.action_type}: ${JSON.stringify(result.payload)}`;
            proposal.hidden = false;
            controls.hidden = false;
            message.textContent = result.message;
        } catch (error) {
            message.textContent = error.message;
        }
    });

    confirmButton.addEventListener("click", async () => {
        if (!actionId) return;
        try {
            const result = await sendAction(`/assistant/actions/${actionId}/confirm/`);
            message.textContent = result.created_type
                ? `Action completed. Created ${result.created_type} ${result.created_id}.`
                : "Action was already completed.";
            controls.hidden = true;
        } catch (error) {
            message.textContent = error.message;
        }
    });

    cancelButton.addEventListener("click", async () => {
        if (!actionId) return;
        try {
            await sendAction(`/assistant/actions/${actionId}/cancel/`);
            message.textContent = "Proposed action cancelled; no change was made.";
            controls.hidden = true;
        } catch (error) {
            message.textContent = error.message;
        }
    });
});
