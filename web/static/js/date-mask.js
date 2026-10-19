document.addEventListener("alpine:init", () => {
  Alpine.data("dateMask", () => ({
    format(event) {
      const input = event.target;
      const digits = input.value.replace(/\D/g, "").slice(0, 8);
      const isDeleting = event.inputType?.startsWith("delete");
      let value = digits.slice(0, 2);

      if (digits.length > 2 || (digits.length === 2 && !isDeleting)) {
        value += "/";
      }

      if (digits.length > 2) {
        value += digits.slice(2, 4);
      }

      if (digits.length > 4 || (digits.length === 4 && !isDeleting)) {
        value += "/";
      }

      if (digits.length > 4) {
        value += digits.slice(4);
      }

      input.value = value;
    },
  }));
});
