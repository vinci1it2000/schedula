import {useMemo} from "react";


export const domainDomain = ({children, render, select, domain, ...props}) => {
    if (!select) {
        const {formContext: {form}} = render
        return form.compileFunc(domain)(render)
    }
    return true
}
export default function Domain({children, render, domain, select, ...props}) {
    const {formContext: {form}} = render
    const func = useMemo(() => (form.compileFunc(domain)), [domain]);
    const index = func(render)
    const status = index > 0 || index === 0
    return status ?
        <div {...props}>{select ? children[index] : children}</div> : null
}