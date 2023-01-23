import ReactAntdown from 'react-antdown'
import formatMd from '../../../../core/utils/Markdown'

export default function Markdown({children, render, ...props}) {
    return (<ReactAntdown>{formatMd({
        children, formData: render.formData, ...props
    })}</ReactAntdown>);
}