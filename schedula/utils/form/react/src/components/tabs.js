import * as React from 'react';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import Box from '@mui/material/Box';



function TabPanel(props) {
    const {children, value, index, ...other} = props;

    return (
        <div
            role="tabpanel"
            hidden={value !== index}
            id={`tabpanel-${index}`}
            aria-labelledby={`tab-${index}`}
            style={{display:"contents"}}
            {...other}
        >
            {value === index &&
            <Box sx={{p: 3, width: "100%"}}>{children} </Box>}
        </div>
    );
}

function a11yProps(index) {
    return {
        id: `tab-${index}`,
        'aria-controls': `tabpanel-${index}`,
    };
}

export default function _tabs(props) {
    const [value, setValue] = React.useState(0);

    const handleChange = (event, newValue) => {
        setValue(newValue);
    };
    return (<React.Fragment>
        <Tabs
            value={value}
            onChange={handleChange}
            sx={{borderRight: 1, borderColor: 'divider'}}{...props}
        >
            {props.children.map((element, index) => (
                <Tab key={index} label={element.props.schema.title || `tab ${index}`} {...a11yProps(index)} />
            ))}
        </Tabs>
        {props.children.map((element, index) => (
            <TabPanel key={index} value={value} index={index}>
                {element}
            </TabPanel>
        ))}
    </React.Fragment>)
}
