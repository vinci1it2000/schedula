import {useEffect, useState} from "react";
import xlsxPreview from 'xlsx-preview';


function dataURLtoFile(dataurl) {
    let arr = dataurl.split(','),
        mime = arr[0].match(/:(.*?);/)[1],
        filename = decodeURIComponent(arr[0].match(/;?name=(.*?);/)[1]),
        bstr = atob(arr[1]),
        n = bstr.length,
        u8arr = new Uint8Array(n);

    while (n--) {
        u8arr[n] = bstr.charCodeAt(n);
    }
    return new File([u8arr], filename, {type: mime});
}


export default function ExcelPreview({children, render, uri, ...props}) {
    const [url, setUrl] = useState(null)
    useEffect(() => {
        if (uri)
            (async () => {
                const result = await xlsxPreview.xlsx2Html(dataURLtoFile(uri), {
                    output: 'arrayBuffer',
                    minimumRows: 50,
                    minimumCols: 30,
                    separateSheets: false
                });
                const url = URL.createObjectURL(new Blob([result], {
                    type: 'text/html'
                }));
                setUrl(url);
            })();
    }, [uri]);
    return <>{url ? <object
        style={{height: '100%', width: '100%'}}
        className="res-obj"
        type="text/html" data={url}
    /> : null}</>

}