import {Statistic} from 'antd';
import {getUiOptions} from "@rjsf/utils";

export default function StatisticField({uiSchema, formData}) {
    const options = getUiOptions(uiSchema);
    return <Statistic value={formData} {...options}/>
}