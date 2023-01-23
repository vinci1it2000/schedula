import {QRCode} from 'antd';
import {getUiOptions} from "@rjsf/utils";

export default function QRCodeField({uiSchema, formData}) {
    const options = getUiOptions(uiSchema);
    return <QRCode value={formData} {...options}/>
}