document.addEventListener("alpine:init", () => {
  Alpine.data("phoneMask", () => ({
    format(event) {
      const input = event.target;
      const digits = input.value.replace(/\D/g, "").slice(0, 15);

      if (digits.length > 11) {
        input.value = digits;
        return;
      }

      let value = digits;

      if (digits.length > 2) {
        value = `(${digits.slice(0, 2)}) ${digits.slice(2)}`;
      } else if (digits.length > 0) {
        value = `(${digits}`;
      }

      const hyphenPosition = digits.length === 11 ? 7 : 6;
      if (digits.length > hyphenPosition) {
        const prefix = digits.slice(2, hyphenPosition);
        const suffix = digits.slice(hyphenPosition);
        value = `(${digits.slice(0, 2)}) ${prefix}-${suffix}`;
      }

      input.value = value;
    },
  }));
});
