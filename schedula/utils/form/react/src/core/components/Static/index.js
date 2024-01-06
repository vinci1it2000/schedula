import {useEffect, useState} from "react";
import DOMPurify from 'dompurify';

export default function Static({children, render, sanitize, url, ...props}) {
    const [html, setHTML] = useState(null)

    useEffect(() => {
        if (url) {
            fetch(url).then(r => r.text()).then(text => {
                if (sanitize)
                    text = DOMPurify.sanitize(text, sanitize)
                setHTML(text)
            })
        } else {
            let text = children.join('')
            if (sanitize)
                text = DOMPurify.sanitize(text, sanitize)
            setHTML(text)
        }
    }, [url, children, sanitize])

    return html ?
        <div {...props} dangerouslySetInnerHTML={{__html: html}}/> : null
}