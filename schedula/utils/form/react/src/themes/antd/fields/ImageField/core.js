import {Image} from 'antd';
import {getUiOptions} from "@rjsf/utils";

export default function ImageField({uiSchema, formData}) {
    const options = getUiOptions(uiSchema);
    return <Image src={formData} {...options}/>
}