// Affiche ou masque les champs de création de compte en fonction de la case cocher.
document.addEventListener("DOMContentLoaded", function () {
    function toggleRow(row) {
        const checkbox = row.querySelector(
            'input[name$="-creer_compte"]',
        );

        if (!checkbox) {
            return;
        }

        const show = checkbox.checked;

        ["username", "password1", "password2", "actif"].forEach(
            function (field) {
                const element = row.querySelector(".field-" + field);

                if (element) {
                    element.style.display = show ? "" : "none";
                }
            },
        );
    }

    function initAll() {
        document
            .querySelectorAll(
                ".inline-group .form-row, .inline-group tr.form-row",
            )
            .forEach(function (row) {
                toggleRow(row);

                const checkbox = row.querySelector(
                    'input[name$="-creer_compte"]',
                );

                if (checkbox && !checkbox.dataset.bound) {
                    checkbox.dataset.bound = "1";

                    checkbox.addEventListener("change", function () {
                        toggleRow(row);
                    });
                }
            });
    }

    initAll();

    const addButton = document.querySelector(
        ".inline-group .add-row a",
    );

    if (addButton) {
        addButton.addEventListener("click", function () {
            setTimeout(initAll, 100);
        });
    }
});