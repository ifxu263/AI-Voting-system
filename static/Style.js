// Additional custom client-side validation logic if needed
document.addEventListener('DOMContentLoaded', () => {
    // Add active feedback on image input preview if available
    const fileInput = document.querySelector('input[type="file"]');
    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            const fileName = e.target.files[0]?.name;
            if (fileName) {
                console.log(`Selected facial image: ${fileName}`);
            }
        });
    }
});
