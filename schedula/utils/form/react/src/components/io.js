import React, {Suspense} from "react";
const Button = React.lazy(() => import("@mui/material/Button"));
const FileUploadOutlinedIcon = React.lazy(() => import("@mui/icons-material/FileUploadOutlined"));
const FileDownloadOutlinedIcon = React.lazy(() => import("@mui/icons-material/FileDownloadOutlined"));

export function exportJson({data, fileName}) {
    // Create a blob with the data we want to download as a file
    const blob = new Blob([JSON.stringify(data)], {type: 'text/json'})
    // Create an anchor element and dispatch a click event on it
    // to trigger a download
    const a = document.createElement('a')
    a.download = fileName
    a.href = window.URL.createObjectURL(blob)
    const clickEvt = new MouseEvent('click', {
        view: window,
        bubbles: true,
        cancelable: true,
    })
    a.dispatchEvent(clickEvt)
    a.remove()
}


export class JSONUpload extends React.Component {
    render() {
        let upload = (event) => {
            event.preventDefault();
            if (event.target.files.length) {
                const reader = new FileReader()
                reader.onload = async ({target}) => {
                    this.props.context.props.onChange(JSON.parse(target.result))
                }
                reader.readAsText(event.target.files[0]);
                event.target.value = null;
            }
        }
        return (<Suspense>
            <Button component={'label'} color="primary"
                    startIcon={<FileUploadOutlinedIcon/>}>
                Import
                <input accept={['json']} type={'file'} hidden
                       onChange={upload}></input>
            </Button>
        </Suspense>)
    }
}

export class JSONExport extends React.Component {
    render() {
        return (<Suspense>
            <Button color="primary"
                    startIcon={<FileDownloadOutlinedIcon/>} onClick={() => {
                exportJson({
                    data: this.props.context.props.formData,
                    fileName: `${this.props.context.props.name || 'file'}.json`
                })
            }}>Export</Button>
        </Suspense>)
    }
}