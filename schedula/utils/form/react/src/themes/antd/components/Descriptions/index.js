import {Descriptions as BaseDescriptions} from 'antd';

const Descriptions = ({children, render, ...props}) => {
    return <BaseDescriptions {...props}>
        {children}
    </BaseDescriptions>
};
export default Descriptions;