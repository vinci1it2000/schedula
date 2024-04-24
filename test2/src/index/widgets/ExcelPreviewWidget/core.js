import ExcelPreview from '../../formContext/components/ExcelPreview'

export default function ExcelPreviewWidget({value, options, ...props}) {
    return <ExcelPreview uri={value} {...options}/>
}