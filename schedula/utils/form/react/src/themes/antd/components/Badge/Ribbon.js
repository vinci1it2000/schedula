import {Badge} from 'antd';

const {Ribbon: BaseRibbon} = Badge,
    Ribbon = ({children, render, ...props}) => (
        <BaseRibbon {...props}>
            {children}
        </BaseRibbon>);
export default Ribbon;