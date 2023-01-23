import {useMemo} from "react";
import {nanoid} from "nanoid";

const Debug = ({children, render, ...props}) => {
    const {form} = render.formContext
    const {debugUrl} = form.state
    return useMemo(() => (debugUrl ? <iframe
        title={nanoid()}
        src={debugUrl}
        allowFullScreen
        style={{
            height: '100%',
            width: '100%',
            border: "none"
        }}
        {...props}/> : null), [debugUrl, props])
}
export const domainDebug = ({children, render, ...props}) => {
    const {form} = render.formContext
    const {debugUrl} = form.state
    return !!debugUrl
}

export default Debug;