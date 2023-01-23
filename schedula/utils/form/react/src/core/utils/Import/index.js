const uploadJSON = (onChange, event) => {
    event.preventDefault();
    if (event.target.files.length) {
        const reader = new FileReader()
        reader.onload = async ({target}) => {
            onChange(JSON.parse(target.result))
        }
        reader.readAsText(event.target.files[0]);
        event.target.value = null;
    }
};

export default uploadJSON