import {useEffect, useRef, useState} from "react";
import UniverSheet from "./components/UniverSheet";
import xtos from "./xtos";

export default function ExcelPreview({children, render, uri, ...props}) {
    const ref = useRef(null)
    const [data, setData] = useState(null)
    useEffect(() => {
        if (uri) {
            (async () => {
                setData(await xtos(uri))
            })();
        } else {
            setData(null)
        }
    }, [uri])
    return data ? <UniverSheet ref={ref} data={data} {...props}/> : null
}