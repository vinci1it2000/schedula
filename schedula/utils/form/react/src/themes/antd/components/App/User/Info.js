import {Descriptions} from 'antd';

const InfoForm = ({userInfo}) => {
    return <Descriptions size={"small"} column={1}>
        {Object.entries(userInfo).map(([label, value], index) => (
            <Descriptions.Item key={index} label={label}>
                {value}
            </Descriptions.Item>
        ))}
    </Descriptions>
}
export default InfoForm;