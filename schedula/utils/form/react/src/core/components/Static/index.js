import {useEffect, useState} from "react";
import DOMPurify from 'dompurify';

export default function Static({children, render, sanitize, url, ...props}) {
    const [html, setHTML] = useState(null)
    const {formContext} = render
    const {form} = formContext
    useEffect(() => {
        if (url) {
            form.postData({
                url,
                method: 'GET'
            }, ({data: text}) => {
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
    }, [url, children, sanitize, form])

    return html ?
        <div {...props} dangerouslySetInnerHTML={{__html: html}}/> : null
}